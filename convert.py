import spacy
from spacy.tokens import DocBin

def convert_conll_to_spacy(conll_file, output_file):
    nlp = spacy.blank("en")  # Create a blank English model
    doc_bin = DocBin()  # To store multiple Doc objects

    with open(conll_file, 'r', encoding='utf-8') as file:
        sentences = []
        current_sentence = []
        current_tags = []
        for line in file:
            line = line.strip()
            if line == "":
                if current_sentence:
                    sentences.append((current_sentence, current_tags))
                    current_sentence = []
                    current_tags = []
            else:
                token, tag = line.split()[:2]
                current_sentence.append(token)
                current_tags.append(tag)

        # Add the final sentence if the file doesn't end with a blank line
        if current_sentence:
            sentences.append((current_sentence, current_tags))

    for tokens, tags in sentences:
        doc = nlp.make_doc(" ".join(tokens))
        ents = []
        start = 0
        for token, tag in zip(tokens, tags):
            end = start + len(token)
            if tag.startswith("B-"):
                label = tag[2:]
                ents.append((start, end, label))
            elif tag.startswith("I-"):
                # Extend the previous entity
                ents[-1] = (ents[-1][0], end, ents[-1][2])
            start = end + 1  # Account for space

        doc.ents = [doc.char_span(start, end, label=label) for start, end, label in ents]
        doc_bin.add(doc)

    doc_bin.to_disk(output_file)
    print(f"Saved SpaCy training data to {output_file}")

convert_conll_to_spacy("con123.conll", "spacy_train_data.spacy")
