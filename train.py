import spacy
from spacy.training.example import Example
from spacy.tokens import DocBin

def train_ner_model(train_data_file, output_dir, epochs=10):
    # Load a blank English model
    nlp = spacy.blank("en")
    if "ner" not in nlp.pipe_names:
        ner = nlp.add_pipe("ner")

    # Load training data
    doc_bin = DocBin().from_disk(train_data_file)
    training_data = list(doc_bin.get_docs(nlp.vocab))

    # Add labels to the NER pipeline
    for doc in training_data:
        for ent in doc.ents:
            ner.add_label(ent.label_)

    # Prepare the training loop
    optimizer = nlp.begin_training()
    for epoch in range(epochs):
        losses = {}
        for doc in training_data:
            example = Example.from_dict(doc, {"entities": [(ent.start_char, ent.end_char, ent.label_) for ent in doc.ents]})
            nlp.update([example], drop=0.1, losses=losses)
        print(f"Epoch {epoch + 1}/{epochs}, Loss: {losses['ner']}")

    # Save the trained model
    nlp.to_disk(output_dir)
    print(f"Saved trained model to {output_dir}")

train_ner_model("spacy_train_data.spacy", "trained_ner_model", epochs=10)
