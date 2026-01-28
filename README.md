# synbiont

**Synbiont is the semantic layer for Synapse.** It provides a shared, evolving ontology that describes the [research data lifecycle](https://www.nnlm.gov/guides/data-glossary/research-lifecycle) and data governance especially in relation to Synapse. A formal model of how data is organized, governed, and related can be more readily consumed by applications, AI agents, and workflows that interact with Synapse repository services. Ideally, the synbiont ontology facilitates mutualism between applications/AI agents/workflows and Synapse: these clients are able to make use of Synapse services efficiently and with a better user experience, while the Synapse repository gains more data and also benefits from more correct, efficent usage.   

## Ontology Notes

The ontology is developed with the [OWL 2 RL profile](https://www.w3.org/TR/owl2-profiles/#Introduction) in mind, which enables scalable reasoning without sacrificing too much expressive power. This selection is based on application needs and the fact that many rule-based reasoning engines are available to implement OWL 2 RL reasoning systems. Here, ontology reasoning is encoded using [N3](https://w3c.github.io/N3/spec/), and [eyeling.js](https://github.com/eyereasoner/eyeling) is used for demonstration of the overall reasoning system.

In addition to the ontology product itself, this repo contains example web and AI agent applications to demonstrate synbiont usage ([see WIP Example applications](#example-applications-wip)). 

We build the ontology in layers: first by lifting authoritative references (OpenAPI, governance spreadsheets, external ontologies) into module files, and then by adding separate modules that impose hand-authored constraints and relationships that tie the references together. Keeping these layers distinct makes it easy to refresh imported sources without losing curated axioms. Tests ensure layers are consistent with any update (WIP).

Examples of relations added in the second layer: 
- Connecting a governance class such as "ControlledAccess" to the Synapse services that help implement it
- Connecting governance classes to other ontologies like DUO; for example, "RestrictedorLimited" is linked to known DUO restrictions. 
- Connecting classes to the standard upper-level OBO ontologies BFO and IAO for interoperability

## Visualization

TBD

## Organization

- [ontology/modules](ontology/modules): Turtle (.ttl) or .n3 source modules that compose the ontology.
- [ontology/imports](ontology/imports): Imported external ontologies (for example, DUO) used during builds.
- [ontology/shacl](ontology/shacl): SHACL validation/constraint definitions aligned with the ontology.
- [scripts](scripts): Utilities such as [ROBOT](https://robot.obolibrary.org/) workflows or ontology import helpers.
- [doc](doc): Reference docs, bootstrapping notes, and design rationale that complement and contextualize the ontology artifacts.

### Example Use Cases

1. Map Synapse Access Restrictions (ARs) to the data types that must comply with each restriction.
2. Trace which Synapse services support each stage of the data lifecycle.
3. Identify the partner processing platforms available for each data type.

## Example applications (WIP)

### "Smart" Task Dashboard

example-apps/smart-dashboard

What would normally be a Todo MVP app becomes a "smart" dashboard using the embedded ontology + reasoner (eyeling.js) to automate: 

- Creation of appropriate governance followup questionnaires based on planned data.
- Classification of data into potential access level tiers.
- Update of dataset status tracker view based on present task entities.
- When data survey results are updated (for fields that can be updated), update or remove downstream tasks.

### A/B AI agent

example-apps/ab-ai-agent

This application is meant to demonstrate the ontology's utility for AI agents, making agents more competent and reliable when helping users manage data. A user asks a question that is given to both agents "A" and "B". All things are the same (provider model, system prompt, request received) *except* that "A" has guidance from the ontology, while "B" does not. The "A" agent is expected to have better performance because it can use the ontology to follow standard/expected data management practices, provide better explanations, make overall fewer false starts/incorrect calls (access resources more efficiently).
