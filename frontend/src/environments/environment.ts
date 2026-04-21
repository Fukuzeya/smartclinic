export const environment = {
  production: false,
  keycloak: {
    url: 'http://localhost:8080',
    realm: 'smartclinic',
    clientId: 'smartclinic-web',
  },
  api: {
    patientIdentity: 'http://localhost:8001',
    scheduling: 'http://localhost:8002',
    clinical: 'http://localhost:8003',
    pharmacy: 'http://localhost:8004',
    laboratory: 'http://localhost:8005',
    billing: 'http://localhost:8006',
    saga: 'http://localhost:8007',
  },
};
