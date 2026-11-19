import type { INodeProperties } from 'n8n-workflow';

const startsJob = { resource: ['media', 'transcript', 'metadata'] };

const waitOptions = (defaultTimeout: number): INodeProperties[] => [
	{
		displayName: 'Poll Interval (Seconds)',
		name: 'pollInterval',
		type: 'number',
		typeOptions: { minValue: 1 },
		default: 5,
		description: 'How often to check the job while waiting for it to finish',
	},
	{
		displayName: 'Timeout (Seconds)',
		name: 'timeout',
		type: 'number',
		typeOptions: { minValue: 10 },
		default: defaultTimeout,
		description:
			'How long to wait for the job before the node fails. The job keeps running, so you can still read it later with Job > Get Status.',
	},
];

export const resourceProperty: INodeProperties = {
	displayName: 'Resource',
	name: 'resource',
	type: 'options',
	noDataExpression: true,
	options: [
		{ name: 'Account', value: 'account' },
		{ name: 'Job', value: 'job' },
		{ name: 'Media', value: 'media' },
		{ name: 'Metadata', value: 'metadata' },
		{ name: 'Transcript', value: 'transcript' },
	],
	default: 'media',
};

export const operationProperties: INodeProperties[] = [
	{
		displayName: 'Operation',
		name: 'operation',
		type: 'options',
		noDataExpression: true,
		displayOptions: { show: { resource: ['media'] } },
		options: [
			{
				name: 'Import',
				value: 'import',
				description:
					'Download the video or audio at a link, optionally as a file for the next node',
				action: 'Import media from a link',
			},
		],
		default: 'import',
	},
	{
		displayName: 'Operation',
		name: 'operation',
		type: 'options',
		noDataExpression: true,
		displayOptions: { show: { resource: ['transcript'] } },
		options: [
			{
				name: 'Get',
				value: 'get',
				description: 'Get the transcript of a video or audio link, with timestamps',
				action: 'Get a transcript',
			},
		],
		default: 'get',
	},
	{
		displayName: 'Operation',
		name: 'operation',
		type: 'options',
		noDataExpression: true,
		displayOptions: { show: { resource: ['metadata'] } },
		options: [
			{
				name: 'Get',
				value: 'get',
				description: 'Get title, description, uploader, stats, tags and formats for a link',
				action: 'Get metadata',
			},
			{
				name: 'Get Basic',
				value: 'getBasic',
				description: 'Get only the title, duration and thumbnail (faster)',
				action: 'Get basic metadata',
			},
		],
		default: 'get',
	},
	{
		displayName: 'Operation',
		name: 'operation',
		type: 'options',
		noDataExpression: true,
		displayOptions: { show: { resource: ['job'] } },
		options: [
			{
				name: 'Get Status',
				value: 'getStatus',
				description: 'Check a job you started earlier and get its result',
				action: 'Get a job status',
			},
		],
		default: 'getStatus',
	},
	{
		displayName: 'Operation',
		name: 'operation',
		type: 'options',
		noDataExpression: true,
		displayOptions: { show: { resource: ['account'] } },
		options: [
			{
				name: 'Get Balance',
				value: 'getBalance',
				description: 'Get your remaining credit in US dollars',
				action: 'Get the account balance',
			},
		],
		default: 'getBalance',
	},
];

export const fieldProperties: INodeProperties[] = [
	{
		displayName: 'Media URL',
		name: 'url',
		type: 'string',
		required: true,
		default: '',
		placeholder: 'https://www.youtube.com/watch?v=jNQXAC9IVRw',
		description:
			'Link to a public video or audio page, e.g. YouTube, TikTok, Instagram, X or a podcast episode',
		displayOptions: { show: startsJob },
	},
	{
		displayName: 'Wait for Completion',
		name: 'waitForCompletion',
		type: 'boolean',
		default: true,
		description:
			'Whether to wait until the job finishes and output the result. Turn off to output the job ID right away and get the result at a webhook URL.',
		displayOptions: { show: startsJob },
	},
	{
		displayName: 'Webhook URL',
		name: 'webhookUrl',
		type: 'string',
		default: '',
		placeholder: '={{ $execution.resumeUrl }}',
		description:
			'HTTPS URL that receives the result when the job completes or fails. To continue this workflow when it arrives, use {{ $execution.resumeUrl }} and add a Wait node set to "On Webhook Call" (POST) after this node.',
		displayOptions: { show: { ...startsJob, waitForCompletion: [false] } },
	},

	// Media > Import
	{
		displayName: 'Download File',
		name: 'downloadFile',
		type: 'boolean',
		default: true,
		description:
			'Whether to output the file as binary data, ready for Google Drive, S3, Dropbox or any node that takes a file. Turn off to get only the download link (valid for 7 days).',
		displayOptions: {
			show: { resource: ['media'], operation: ['import'], waitForCompletion: [true] },
		},
	},
	{
		displayName: 'Put Output File in Field',
		name: 'binaryPropertyName',
		type: 'string',
		default: 'data',
		required: true,
		description: 'The name of the binary field to put the file in',
		displayOptions: {
			show: {
				resource: ['media'],
				operation: ['import'],
				waitForCompletion: [true],
				downloadFile: [true],
			},
		},
	},
	{
		displayName: 'Options',
		name: 'options',
		type: 'collection',
		placeholder: 'Add Option',
		default: {},
		displayOptions: { show: { resource: ['media'], operation: ['import'] } },
		options: [
			{
				displayName: 'Audio Quality',
				name: 'audioQuality',
				type: 'options',
				options: [
					{ name: 'Best', value: 'best' },
					{ name: 'High (Up to 192 Kbps)', value: 'high' },
					{ name: 'Low (Up to 64 Kbps)', value: 'low' },
					{ name: 'Lowest', value: 'lowest' },
					{ name: 'Medium (Up to 128 Kbps)', value: 'medium' },
				],
				default: 'medium',
			},
			{
				displayName: 'Bucket Filename',
				name: 'storageFilename',
				type: 'string',
				default: '',
				description:
					'Filename in your bucket, without extension. Defaults to the media title. Needs Copy to Your S3 Bucket.',
			},
			{
				displayName: 'Bucket Folder',
				name: 'storagePath',
				type: 'string',
				default: '',
				placeholder: 'videos/2026',
				description:
					'Folder prefix in your bucket. Defaults to the prefix in your S3 settings. Needs Copy to Your S3 Bucket.',
			},
			{
				displayName: 'Copy to Your S3 Bucket',
				name: 'store',
				type: 'boolean',
				default: false,
				description:
					'Whether to also copy the file to your own S3-compatible bucket (S3, R2, B2 and others). Save the bucket once on the Importly dashboard first.',
			},
			{
				displayName: 'Format',
				name: 'format',
				type: 'options',
				options: [
					{ name: 'Video and Audio', value: 'videoAndAudio' },
					{ name: 'Audio Only', value: 'audioOnly' },
					{ name: 'Video Only (No Sound)', value: 'videoOnly' },
				],
				default: 'videoAndAudio',
			},
			{
				displayName: 'Include Transcript',
				name: 'includeTranscript',
				type: 'boolean',
				default: false,
				description: 'Whether to also return the transcript from the same job',
			},
			{
				displayName: 'Max Cost (USD)',
				name: 'maxCostDollars',
				type: 'number',
				typeOptions: { minValue: 0.01, numberPrecision: 2 },
				default: 0.5,
				description:
					'The most this request may cost. If it would cost more, nothing is downloaded and the job fails with the price.',
			},
			{
				displayName: 'Transcript Language',
				name: 'transcriptLanguage',
				type: 'string',
				default: '',
				placeholder: 'en',
				description: 'Two-letter language code for the transcript, e.g. es',
			},
			{
				displayName: 'Video Quality',
				name: 'videoQuality',
				type: 'options',
				options: [
					{ name: '1080p', value: '1080p' },
					{ name: '1440p', value: '1440p' },
					{ name: '144p', value: '144p' },
					{ name: '2160p (4K)', value: '2160p' },
					{ name: '240p', value: '240p' },
					{ name: '360p', value: '360p' },
					{ name: '480p', value: '480p' },
					{ name: '720p', value: '720p' },
					{ name: 'Best', value: 'best' },
					{ name: 'Lowest', value: 'lowest' },
				],
				default: '720p',
				description: 'Highest resolution to download, measured on the shorter side of the frame',
			},
			...waitOptions(600),
		],
	},

	// Transcript > Get
	{
		displayName: 'Options',
		name: 'options',
		type: 'collection',
		placeholder: 'Add Option',
		default: {},
		displayOptions: { show: { resource: ['transcript'], operation: ['get'] } },
		options: [
			{
				displayName: 'Include Segments',
				name: 'includeSegments',
				type: 'boolean',
				default: true,
				description: 'Whether to include the timestamped segments as well as the plain text',
			},
			{
				displayName: 'Language',
				name: 'language',
				type: 'string',
				default: '',
				placeholder: 'en',
				description:
					'Two-letter language code, e.g. es. Picks the caption track or the spoken language.',
			},
			{
				displayName: 'Max Cost (USD)',
				name: 'maxCostDollars',
				type: 'number',
				typeOptions: { minValue: 0.01, numberPrecision: 2 },
				default: 1,
				description:
					'Cap for speech-to-text. If it would cost more, the job fails with the estimate.',
			},
			{
				displayName: 'Source',
				name: 'provider',
				type: 'options',
				options: [
					{
						name: 'AssemblyAI (Key Saved in Importly)',
						value: 'assemblyai',
					},
					{
						name: 'Deepgram (Key Saved in Importly)',
						value: 'deepgram',
					},
					{
						name: 'Existing Captions',
						value: 'captions',
						description: 'Use the video’s captions, including auto-generated ones. Cheapest.',
					},
					{
						name: 'Importly Speech-to-Text',
						value: 'importly',
						description:
							'Transcribe the audio, for videos without captions. No extra account needed.',
					},
					{
						name: 'OpenAI (Key Saved in Importly)',
						value: 'openai',
					},
				],
				default: 'captions',
			},
			...waitOptions(600),
		],
	},

	// Metadata > Get
	{
		displayName: 'Simplify',
		name: 'simplify',
		type: 'boolean',
		default: true,
		description:
			'Whether to return a simplified version of the response instead of the raw data (about 80 fields, including every format)',
		displayOptions: {
			show: { resource: ['metadata'], operation: ['get'], waitForCompletion: [true] },
		},
	},
	{
		displayName: 'Options',
		name: 'options',
		type: 'collection',
		placeholder: 'Add Option',
		default: {},
		displayOptions: { show: { resource: ['metadata'] } },
		options: [...waitOptions(120)],
	},

	// Job > Get Status
	{
		displayName: 'Job Type',
		name: 'jobType',
		type: 'options',
		options: [
			{ name: 'Basic Metadata', value: 'basicMetadata' },
			{ name: 'Import', value: 'import' },
			{ name: 'Metadata', value: 'metadata' },
			{ name: 'Transcript', value: 'transcript' },
		],
		default: 'import',
		description: 'The kind of job the ID belongs to',
		displayOptions: { show: { resource: ['job'], operation: ['getStatus'] } },
	},
	{
		displayName: 'Job ID',
		name: 'jobId',
		type: 'string',
		required: true,
		default: '',
		placeholder: 'a824760e-ece1-4415-8838-ce2a7785ea6b',
		description: 'The job ID returned when the job was started',
		displayOptions: { show: { resource: ['job'], operation: ['getStatus'] } },
	},
];
