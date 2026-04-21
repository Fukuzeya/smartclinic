// Production environment — Angular app served by the nginx container.
// API calls go through the nginx reverse proxy at /api/<service>.
// Keycloak is accessed directly at localhost:8080 (browser redirect flow).
export const environment = {
  production: true,
  keycloak: {
    url: 'http://localhost:8080',
    realm: 'smartclinic',
    clientId: 'smartclinic-web',
  },
  api: {
    patientIdentity: '/api/patients',
    scheduling: '/api/scheduling',
    clinical: '/api/clinical',
    pharmacy: '/api/pharmacy',
    laboratory: '/api/laboratory',
    billing: '/api/billing',
    saga: '/api/saga',
  },
};
