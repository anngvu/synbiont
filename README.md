# synbiont

**Synbiont is the semantic layer for Synapse.** It provides a shared, evolving ontology that describes standard data management on Synapse -- how data is best organized, governed, and related -- that can be consumed directly by applications, AI agents, and workflows that interact with Synapse repository services. Ideally, the synbiont ontology facilitates mutualism between those applications/AI agents/workflows and Synapse: the first group is able to make use of Synapse services efficiently and with a better user experience, while the Synapse repository gains more data and also benefits from correct, efficent usage.   

## More Details

Using the OWL 2 RL profile enables scalable reasoning without sacrificing too much expressive power ([ref](https://www.w3.org/TR/owl2-profiles)). 

Coming soon: ontology visualization.

In addition to the ontology product itself, this repo contains example applications to demonstrate synbiont usage (see #Example applications). 

## Organization

- `ontology/modules` folder contains the source files in .ttl
- `ontology/shacl` contains SHACL files for validation and constraint checking use cases
- `scripts` contains useful [robot](https://robot.obolibrary.org/) scripts or other scripts helpful for development 
- `doc` contains docs on 

### Examples

### Governance

1. What are types of Access Restrictions does Synapse implement, and what data types are expected to map to each of these restrictions
2. Which Synapse services support each phase of the data lifecycle. 

### Interop

1. Which data processing platforms are integrated with Synapse, which data types can be processed through each of them

## Example applications (WIP)

### "Smart" Todo MVP

example-apps/smart-todo-mvp

The classic Todo MVP app that goes beyond to use the embedded ontology + workflow engine to: 

1. Auto-create appropriate followup governance tasks based on the properties of the first planning task.
2. When a new plan version is created, the visualization auto-updates to visualize values using the new plan.

### AI agent in A/B mode

example-apps/ab-ai-agent

This app can be started in "A" or "B" mode and features an agent to interact with. Logs of agent actions can be seen in the UI. The agent in both modes is the same (provider model, system prompt, mock tools) *except* that in "A" mode the agent also has access to the ontology, while in "B" mode the agent does not. The application can be used for blinded user testing, where experienced users can rate which agent is more competent and reliable.

The "A" mode agent is expected to perform better because it can use the ontology to follow standard data management practices and/or provide grounded explanations. As well, the agent should make overall fewer false starts or incorrect calls, which reduces load on Synapse repository services.

Test cases:

1. When asked whether an entity can be "released", agent will first check that data type and the rules for that data type, then explain why or why or not data can be released. 
2. Explain the rationale for the standard "Data Survey" configuration and how a change breaks something downstream.
3. Correctly advises on which partner platform can handle processing of a data type / how to create the appropriate "Compute Task". 

