// Production environment - Angular app served by the frontend nginx container,
// fronted by Caddy on http://172.236.3.27.
//
// The Keycloak URL must be the PUBLIC one the browser can reach - not the
// internal docker-network name - because the OIDC redirect flow runs entirely
// in the user's browser.
export const environment = {
  production: true,
  keycloak: {
    url: 'http://172.236.3.27/auth',
    realm: 'smartclinic',
    clientId: 'smartclinic-web',
  },
  // API paths go through Caddy - keep these in sync with ops/caddy/Caddyfile.
  api: {
    patientIdentity: '/api/patients',
    scheduling:      '/api/appointments',
    clinical:        '/api/encounters',
    pharmacy:        '/api/prescriptions',
    laboratory:      '/api/lab',
    billing:         '/api/invoices',
    saga:            '/api/saga',
  },
};
