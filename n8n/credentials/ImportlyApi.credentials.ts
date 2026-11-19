import type {
	IAuthenticateGeneric,
	Icon,
	ICredentialTestRequest,
	ICredentialType,
	INodeProperties,
} from 'n8n-workflow';

export class ImportlyApi implements ICredentialType {
	name = 'importlyApi';

	displayName = 'Importly API';

	icon: Icon = { light: 'file:../icons/importly.svg', dark: 'file:../icons/importly.dark.svg' };

	documentationUrl = 'https://www.importly.io/docs/authentication';

	properties: INodeProperties[] = [
		{
			displayName: 'API Key',
			name: 'apiKey',
			type: 'string',
			typeOptions: { password: true },
			required: true,
			default: '',
			description:
				'Your Importly API key, from https://www.importly.io/dashboard/api-key. New accounts are free to try, no card required.',
		},
	];

	authenticate: IAuthenticateGeneric = {
		type: 'generic',
		properties: {
			headers: {
				Authorization: '=Bearer {{$credentials.apiKey}}',
			},
		},
	};

	test: ICredentialTestRequest = {
		request: {
			baseURL: 'https://api.importly.io',
			url: '/balance',
			method: 'GET',
		},
	};
}
