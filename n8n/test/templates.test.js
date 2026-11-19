// Checks the workflow templates in ../templates: valid structure, wiring that points at
// real nodes, no stored credentials, and Importly node parameters the node actually has.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { Importly } = require('../dist/nodes/Importly/Importly.node.js');

const templatesDir = path.join(__dirname, '..', 'templates');
const templates = fs.readdirSync(templatesDir).filter((file) => file.endsWith('.json'));
const description = new Importly().description;
const knownParameters = new Set(description.properties.map((property) => property.name));

function optionsFor(name, resource, operation) {
	return description.properties.filter((property) => {
		if (property.name !== name) return false;
		const show = property.displayOptions?.show ?? {};
		if (show.resource && !show.resource.includes(resource)) return false;
		if (show.operation && !show.operation.includes(operation)) return false;
		return true;
	});
}

test('there are three templates', () => {
	assert.equal(templates.length, 3);
});

for (const file of templates) {
	test(`${file} is a valid, credential-free workflow`, () => {
		const workflow = JSON.parse(fs.readFileSync(path.join(templatesDir, file), 'utf8'));
		assert.ok(workflow.name);
		const names = workflow.nodes.map((node) => node.name);
		assert.equal(new Set(names).size, names.length, 'node names are unique');

		for (const node of workflow.nodes) {
			assert.equal(node.credentials, undefined, `${node.name} has no stored credentials`);
			assert.ok(node.type && node.typeVersion && node.position, `${node.name} is complete`);
		}

		for (const [source, outputs] of Object.entries(workflow.connections)) {
			assert.ok(names.includes(source), `connection source ${source} exists`);
			for (const target of outputs.main.flat()) {
				assert.ok(names.includes(target.node), `connection target ${target.node} exists`);
			}
		}

		const importlyNodes = workflow.nodes.filter(
			(node) => node.type === 'n8n-nodes-importly.importly',
		);
		assert.ok(importlyNodes.length > 0, 'uses the Importly node');
		for (const node of importlyNodes) {
			const { resource, operation, options = {} } = node.parameters;
			const resourceOptions = description.properties.find(
				(property) => property.name === 'resource',
			).options;
			assert.ok(
				resourceOptions.some((option) => option.value === resource),
				`${node.name}: resource`,
			);
			const operationProperty = optionsFor('operation', resource, operation)[0];
			assert.ok(
				operationProperty.options.some((option) => option.value === operation),
				`${node.name}: operation`,
			);
			for (const name of Object.keys(node.parameters)) {
				assert.ok(knownParameters.has(name), `${node.name}: parameter ${name} exists`);
			}
			const optionNames = new Set(
				optionsFor('options', resource, operation).flatMap((property) =>
					property.options.map((option) => option.name),
				),
			);
			for (const name of Object.keys(options)) {
				assert.ok(
					optionNames.has(name),
					`${node.name}: option ${name} exists for ${resource} > ${operation}`,
				);
			}
		}

		const text = JSON.stringify(workflow);
		assert.ok(text.includes('utm_source=n8n'), 'setup note links to Importly with UTMs');
		assert.ok(!/yt-dlp|proxy|proxies/i.test(text), 'no mechanism claims');
	});
}
