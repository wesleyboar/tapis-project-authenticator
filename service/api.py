from flask_migrate import Migrate
from common.config import conf
from common.utils import TapisApi, handle_error, flask_errors_dict

from service import MIGRATIONS_RUNNING
from service.auth import authn_and_authz
from service.controllers import AuthorizeResource, ClientsResource, ClientResource, TokensResource, \
    ProfilesResource, ProfileResource, StaticFilesResource, LoginResource, SetTenantResource, LogoutResource, \
    WebappTokenGen, WebappTokenAndRedirect, TenantConfigResource, UserInfoResource, OAuth2ProviderExtCallback, \
    OAuthMetadataResource, MFAResource
from service.ldap import populate_test_ldap
from service.models import db, app, initialize_tenant_configs

from common.logs import get_logger
logger = get_logger(__name__)

# authentication and authorization ---
@app.before_request
def authnz_for_authenticator():
    authn_and_authz()


# db and migrations ----
db.init_app(app)
migrate = Migrate(app, db)


# create the initial tenantconfig objects for all tenants assigned to this authenticator if they do not exist
# don't run this during migrations
if not MIGRATIONS_RUNNING:
    for tenant_id in conf.tenants:
        initialize_tenant_configs(tenant_id)

# initialize the test LDAP ---
# TODO - this code is run by every thread but is not thread safe!
if conf.populate_dev_ldap:
    populate_test_ldap()


# flask restful API object ----
api = TapisApi(app, errors=flask_errors_dict)

# Set up error handling
api.handle_error = handle_error
api.handle_exception = handle_error
api.handle_user_exception = handle_error

# API resources
api.add_resource(OAuthMetadataResource, '/v3/oauth2/.well-known/oauth-authorization-server')
api.add_resource(TenantConfigResource, '/v3/oauth2/admin/config')
api.add_resource(ClientsResource, '/v3/oauth2/clients')
api.add_resource(ClientResource, '/v3/oauth2/clients/<client_id>')
api.add_resource(TokensResource, '/v3/oauth2/tokens')
api.add_resource(UserInfoResource, '/v3/oauth2/userinfo')
api.add_resource(ProfilesResource, '/v3/oauth2/profiles')
api.add_resource(ProfileResource, '/v3/oauth2/profiles/<username>')

# Auth server resources
api.add_resource(AuthorizeResource, '/v3/oauth2/authorize')
api.add_resource(LoginResource, '/v3/oauth2/login')
api.add_resource(MFAResource, '/v3/oauth2/mfa')
api.add_resource(SetTenantResource, '/v3/oauth2/tenant')
api.add_resource(LogoutResource, '/v3/oauth2/logout')
api.add_resource(OAuth2ProviderExtCallback, '/v3/oauth2/extensions/oa2/callback')

# Portal resources
api.add_resource(WebappTokenGen, '/v3/oauth2/webapp/callback')
api.add_resource(WebappTokenAndRedirect, '/v3/oauth2/webapp')

# Staticfiles
api.add_resource(StaticFilesResource, '/v3/oauth2/authorize/<path>')