import requests
import json
from flask import g, request, Response, render_template, make_response, send_from_directory
from flask import g, request, Response, render_template, redirect, make_response, send_from_directory, session, url_for
from flask_restful import Resource
from openapi_core.shortcuts import RequestValidator
from openapi_core.wrappers.flask import FlaskOpenAPIRequest

from common import utils, errors
from common.config import conf

from service.ldap import list_tenant_users, get_tenant_user, check_username_password
from service.errors import InvalidPasswordError
from service.models import db, Client, Token, AuthorizationCode
from service.ldap import list_tenant_users, get_tenant_user, check_username_password

# get the logger instance -
from common.logs import get_logger
logger = get_logger(__name__)


class ClientsResource(Resource):
    """
    Work with OAuth client objects
    """

    def get(self):
        clients = Client.query.filter_by(tenant_id=g.tenant_id, username=g.username)
        return utils.ok(result=[cl.serialize for cl in clients], msg="Clients retrieved successfully.")

    def post(self):
        validator = RequestValidator(utils.spec)
        result = validator.validate(FlaskOpenAPIRequest(request))
        if result.errors:
            raise errors.ResourceError(msg=f'Invalid POST data: {result.errors}.')
        validated_body = result.body
        data = Client.get_derived_values(validated_body)
        client = Client(**data)
        db.session.add(client)
        db.session.commit()
        return utils.ok(result=client.serialize, msg="Client created successfully.")


class ClientResource(Resource):
    """
    Work with a single OAuth client objects
    """

    def get(self, client_id):
        client = Client.query.filter_by(tenant_id=g.tenant_id, client_id=client_id).first()
        if not client:
            raise errors.ResourceError(msg=f'No client found with id {client_id}.')
        if not client.username == g.username:
            raise errors.PermissionsError("Not authorized for this client.")
        return utils.ok(result=client.serialize, msg='Client object retrieved successfully.')

    def delete(self, client_id):
        client = Client.query.filter_by(tenant_id=g.tenant_id, client_id=client_id).first()
        if not client:
            raise errors.ResourceError(msg=f'No client found with id {client_id}.')
        if not client.username == g.username:
            raise errors.PermissionsError("Not authorized for this client.")
        db.session.delete(client)
        db.session.commit()


class TokensResource(Resource):
    """
    Implements the oauth2/tokens endpoint for generating tokens for the following grant types:
      * password
      * authorization_code
    """

    def post(self):
        validator = RequestValidator(utils.spec)
        result = validator.validate(FlaskOpenAPIRequest(request))
        if result.errors:
            raise errors.ResourceError(msg=f'Invalid POST data: {result.errors}.')
        validated_body = result.body
        logger.debug(f"BODY: {validated_body}")
        data = Token.get_derived_values(validated_body)

        grant_type = data['grant_type']
        if not grant_type:
            raise errors.ResourceError(msg=f'Missing the required grant_type parameter.')

        tenant_id = g.request_tenant_id
        # get headers
        try:
            auth = request.authorization
            client_id = auth.username
            client_key = auth.password
        except Exception as e:
            raise errors.ResourceError(msg=f'Invalid headers. Basic authentication with client id and k'
                                           f'ey required but missing.')
        # check that client is in db
        logger.debug("Checking that client exists.")
        client = Client.query.filter_by(tenant_id=tenant_id, client_id=client_id, client_key=client_key).first()
        if not client:
            raise errors.ResourceError(msg=f'Invalid client credentials: {client_id}, {client_key}.')
        # check grant type:
        if grant_type == 'password':
            # validate user/pass against ldap
            username = data.get('username')
            password = data.get('password')
            if not username or not password:
                raise errors.ResourceError("Missing requried payload data; username and password are required for "
                                           "the password grant type.")
            check_ldap = check_username_password(tenant_id, username, password)
            logger.debug(f"returned: {check_ldap}")
        elif grant_type == 'authorization_code':
            # check the redirect uri -
            redirect_uri = data.get('redirect_uri')
            if not redirect_uri:
                raise errors.ResourceError("Required redirect_uri parameter missing.")
            if not redirect_uri == client.callback_url:
                raise errors.ResourceError("Invalid redirect_uri parameter: does not match "
                                           "callback URL registered with client.")
            # validate the authorization code
            code = data.get('code')
            if not code:
                raise errors.ResourceError("Required authorization_code parameter missing.")
            AuthorizationCode.validate_code(tenant_id=tenant_id,
                                            code=code,
                                            client_id=client_id,
                                            client_key=client_key)
        else:
            raise errors.ResourceError("Invalid grant_type")

        # call /v3/tokens to generate access token for the user
        url = f'{g.request_tenant_base_url}/v3/tokens'
        content = {
            "token_tenant_id": f"{tenant_id}",
            "account_type": "service",
            "token_username": f"{data['username']}",
        }
        r = requests.post(url, json=content)
        json_resp = json.loads(r.text)

        return utils.ok(result=json_resp, msg="Token created successfully.")


class ProfilesResource(Resource):
    """
    Work with profiles.
    """

    def get(self):
        logger.debug('top of GET /profiles')
        # get the tenant id - we use the x_tapis_tenant if that is set (from some service account); otherwise, we use
        # the tenant_id assoicated with the JWT.
        tenant_id = getattr(g, 'x_tapis_tenant', None)
        if not tenant_id:
            logger.debug("didn't find x_tapis_tenant; using tenant id in token.")
            tenant_id = g.tenant_id
        logger.debug(f"using tenant_id {tenant_id}")
        try:
            limit = int(request.args.get('limit'))
        except:
            limit = None
        offset = 0
        try:
            offset = int(request.args.get('offset'))
        except Exception as e:
            logger.debug(f'get exception parsing offset; exception: {e}; setting offset to none.')
        users, offset = list_tenant_users(tenant_id=tenant_id, limit=limit, offset=offset)
        resp = utils.ok(result=[u.serialize for u in users], msg="Profiles retrieved successfully.")
        resp.headers['X-Tapis-Offset'] = offset
        return resp


class ProfileResource(Resource):
    def get(self, username):
        logger.debug(f'top of GET /profiles/{username}')
        tenant_id = g.request_tenant_id
        user = get_tenant_user(tenant_id=tenant_id, username=username)
        return utils.ok(result=user.serialize, msg="User profile retrieved successfully.")

def check_client():
    """
    Checks the request for associated client query parameters, validates them against the client registered in the DB
    and returns the associated objects.
    """
    # tenant_id should be determined by the request URL -
    tenant_id = g.request_tenant_id
    if not tenant_id:
        tenant_id = session['tenant_id']
    if not tenant_id:
        raise errors.ResourceError("tenant_id missing.")
    # required query parameters:
    client_id = request.args.get('client_id')
    client_redirect_uri = request.args.get('redirect_uri')
    response_type = request.args.get('response_type')
    # state is optional -
    client_state = request.args.get('state')
    if not client_id:
        raise errors.ResourceError("Required query parameter client_id missing.")
    if not client_redirect_uri:
        raise errors.ResourceError("Required query parameter redirect_uri missing.")
    if not response_type == 'code':
        raise errors.ResourceError("Required query parameter response_type missing or not supported.")
    # make sure the client exists and the redirect_uri matches
    client = Client.query.filter_by(tenant_id=tenant_id, client_id=client_id).first()
    if not client:
        raise errors.ResourceError("Invalid client.")
    if not client.callback_url == client_redirect_uri:
        raise errors.ResourceError(
            "redirect_uri query parameter does not match the registered callback_url for the client.")
    return client_id, client_redirect_uri, client_state, client

class AuthorizeResource(Resource):
    def get(self):
        client_id, client_redirect_uri, client_state, client = check_client()
        if not 'username' in session:
            return redirect(url_for('loginresource',
                                    client_id=client_id,
                                    redirect_uri=client_redirect_uri,
                                    state=client_state,
                                    response_type='code'))
        client_id, client_redirect_uri, client_state, client = check_client()
        headers = {'Content-Type': 'text/html'}
        context = {'error': '',
                   'username': session['username'],
                   'client_display_name': client.display_name,
                   'client_id': client_id,
                   'client_redirect_uri': client_redirect_uri,
                   'client_state': client_state}

        return make_response(render_template('authorize.html',  **context), 200, headers)

    def post(self):
        # selecting a tenant id is required before logging in -
        tenant_id = g.request_tenant_id
        if not tenant_id:
            tenant_id = session['tenant_id']
        if not tenant_id:
            raise errors.ResourceError('Tenant ID missing from session. Please logout and select a tenant.')
        client_display_name = request.form.get('client_display_name')
        approve = request.form.get("approve")
        if not approve:
            headers = {'Content-Type': 'text/html'}
            context = {'error': f'To proceed with authorization application {client_display_name}, you '
                                f'must approve the request.'}
            return make_response(render_template('authorize.html', **context), 200, headers)

        state = request.form.get("state")
        # retrieve client data from form and db -
        client_id = request.form.get('client_id')
        if not client_id:
            raise errors.ResourceError("client_id missing.")
        client = Client.query.filter_by(client_id=client_id).first()
        if not client:
            raise errors.ResourceError('Invalid client.')
        # create the authorization code for the client -
        authz_code = AuthorizationCode(tenant_id=tenant_id,
                                       client_id=client_id,
                                       client_key=client.client_key,
                                       redirect_url=client.callback_url,
                                       code=AuthorizationCode.generate_code(),
                                       expiry_time=AuthorizationCode.compute_expiry())
        # issue redirect to client callback_url with authorization code:
        url = f'{client.callback_url}?code={authz_code}&state={state}'

        return redirect(url)

class SetTenantResource(Resource):
    def get(self):
        headers = {'Content-Type': 'text/html'}
        client_id, client_redirect_uri, client_state, client = check_client()
        context = {'error': '',
                   'client_display_name': client.display_name,
                   'client_id': client_id,
                   'client_redirect_uri': client_redirect_uri,
                   'client_state': client_state}
        return make_response(render_template('tenant.html', **context), 200, headers)

    def post(self):
        tenant_id = request.form.get("tenant")
        logger.debug(f"setting session tenant_id to: {tenant_id}")
        client_id = request.form.get('client_id')
        client_redirect_uri = request.form.get('client_redirect_uri')
        client_state = request.form.get('client_state')
        client_display_name = request.form.get('client_display_name')
        session['tenant_id'] = tenant_id
        return redirect(url_for('loginresource',
                                client_id=client_id,
                                redirect_uri=client_redirect_uri,
                                state=client_state,
                                client_display_name=client_display_name,
                                response_type='code'))


class LoginResource(Resource):
    def get(self):
        client_id, client_redirect_uri, client_state, client = check_client()
        # selecting a tenant id is required before logging in -
        tenant_id = g.request_tenant_id
        if not tenant_id:
            tenant_id = session['tenant_id']
        if not tenant_id:
            logger.debug(f"did not find tenant_id in session; issuing redirect to SetTenantResource. session: {session}")
            return redirect(url_for('settenantresource',
                                    client_id=client_id,
                                    redirect_uri=client_redirect_uri,
                                    state=client_state,
                                    response_type='code'))
        headers = {'Content-Type': 'text/html'}
        context = {'error': '',
                   'client_display_name': client.display_name,
                   'client_id': client_id,
                   'client_redirect_uri': client_redirect_uri,
                   'client_state': client_state,
                   'tenant_id': tenant_id}
        return make_response(render_template('login.html', **context), 200, headers)

    def post(self):
        # process the login form -
        tenant_id = g.request_tenant_id
        if not tenant_id:
            tenant_id = session['tenant_id']
        if not tenant_id:
            client_id, client_redirect_uri, client_state, client = check_client()
            logger.debug(f"did not find tenant_id in session; issuing redirect to SetTenantResource. session: {session}")
            raise errors.ResourceError("Invalid session; please return to the original application or logout of this session.")
        headers = {'Content-Type': 'text/html'}
        username = request.form.get("username")
        if not username:
            error = 'Username is required.'
            return make_response(render_template('login.html', **{'error': error}), 200, headers)
        password = request.form.get("password")
        if not password:
            error = 'Password is required.'
        try:
            check_username_password(tenant_id=tenant_id, username=username, password=password)
        except InvalidPasswordError:
            error = 'Invalid username/password combination.'
            return make_response(render_template('login.html', **{'error': error}), 200, headers)
        # the username and password were accepted; set the session and redirect to the authorization page.
        session['username'] = username
        client_id = request.form.get('client_id')
        client_redirect_uri = request.form.get('client_redirect_uri')
        client_state = request.form.get('client_state')
        client_display_name = request.form.get('client_display_name')

        return redirect(url_for('authorizeresource',
                                client_id=client_id,
                                redirect_uri=client_redirect_uri,
                                state=client_state,
                                client_display_name=client_display_name,
                                response_type='code'))


class LogoutResource(Resource):

    def get(self):
        # selecting a tenant id is required before logging in -
        headers = {'Content-Type': 'text/html'}
        tenant_id = g.request_tenant_id
        if not tenant_id:
            tenant_id = session['tenant_id']
        if not tenant_id:
            logger.debug(f"did not find tenant_id in session; issuing redirect to SetTenantResource. session: {session}")
            # reset the session in case there is some weird cruft
            session.pop('username', None)
            session.pop('tenant_id', None)
            make_response(render_template('logout.html', logout_message='You have been logged out.'), 200, headers)
        return make_response(render_template('logout.html'), 200, headers)

    def post(self):
        headers = {'Content-Type': 'text/html'}
        # process the logout form -
        if request.form.get("logout"):
            session.pop('username', None)
            session.pop('tenant_id', None)
            make_response(render_template('logout.html', logout_message='You have been logged out.'), 200, headers)
        # if they submitted the logout form but did not check the box then just return them to the logout form -
        return redirect(url_for('logoutresource'))


class StaticFilesResource(Resource):
    def get(self, path):
        return send_from_directory('templates', path)


##### Webapp Views #####

class WebappRedirect(Resource):
# /oauth2/webapp/index.html
    def get(self):
        # Make sure test client exists
        data = {
            "client_id": conf.dev_client_id,
            "client_key": conf.dev_client_key,
            "callback_url": conf.dev_client_callback,
            "display_name": conf.dev_client_display_name
        }
        client = Client.query.filter_by(
            client_id=conf.dev_client_id,
            client_key=conf.dev_client_key
        )
        if not client:
            client = Client(**data)
            db.session.add(client)
            db.session.commit()

        # check if session exists
        logger.debug(f'LOOK HERE {client}')
        # if not, redirect to login (oauth2/authorize)
            # maybe pass csrf token as well (state var)
            # get tenant_id based on url

        return "test"


class WebappTokenGen(Resource):
# /oauth2/webapp/callback
    def get(self):
        # Get query parameters from request

        # Receive the code (and state if passed)

        #  POST to oauth2/tokens (passing code, client id, client secret, and redirect uri)
            # redirect uri is just callback url

        # Get token from POST response

        #  Redirect to oauth2/webapp/token-display
        pass

class WebappTokenDisplay(Resource):
# /oauth2/webapp/token-display
    def get(self):
        # Get token from request
        # Display token to user
        pass