import PyPDF2
import spacy
import pandas as pd
import re
import streamlit as st

# Load the SpaCy English model
nlp = spacy.load('en_core_web_md')

def extract_keyword_info(pdf_path, keywords, surrounding_sentences_count=2):
    keywords = [keyword.lower() for keyword in keywords]  # Convert keywords to lowercase
    extracted_data = {}

    # Open the PDF file
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)

        # Iterate through the pages
        for page_number in range(len(reader.pages)):
            page = reader.pages[page_number]
            text = page.extract_text()

            if text:
                # Process the text with SpaCy to create a document object
                doc = nlp(text)

                # Tokenize into sentences
                sentences = [sent.text for sent in doc.sents]

                # Find sentences containing any of the keywords
                matching_sentences = []
                for idx, sentence in enumerate(sentences):
                    if any(keyword in sentence.lower() for keyword in keywords):
                        # Extract surrounding sentences for context
                        start_idx = max(0, idx - surrounding_sentences_count)
                        end_idx = min(len(sentences), idx + surrounding_sentences_count + 1)
                        surrounding = sentences[start_idx:end_idx]
                        
                        # Highlight keywords in the sentence
                        highlighted_sentence = highlight_keywords(sentence, keywords)
                        
                        matching_sentences.append({
                            "sentence": highlighted_sentence,
                            "surrounding_context": surrounding,
                            "page_number": page_number + 1
                        })

                if matching_sentences:
                    extracted_data[page_number + 1] = matching_sentences

    return extracted_data

def highlight_keywords(text, keywords):
    """Highlight keywords in the sentence"""
    for keyword in keywords:
        text = re.sub(f'({re.escape(keyword)})', r'<b style="color: red;">\1</b>', text, flags=re.IGNORECASE)
    return text

def display_results(keyword_results):
    # Display results for keyword search
    for keyword in keyword_results:
        with st.expander(f"**🔍 Keyword: {keyword}**", expanded=True):  # Expandable panel for each keyword
            st.markdown(f"### **Keyword: {keyword}**")

            # Display all matched sentences for this keyword
            if keyword in keyword_results:
                st.subheader(f"**Matched Sentences for {keyword}:**")
                for page, matches in keyword_results[keyword].items():  # Keyword results are stored per page number
                    for match in matches:
                        st.markdown(f"#### **Matched Sentence on Page {match['page_number']}:**")
                        st.markdown(f"<p style='color: #00C0F9;'>{match['sentence']}</p>", unsafe_allow_html=True)
                        st.write("**Context**:")
                        for context_sentence in match['surrounding_context']:
                            st.write(f"  - {context_sentence}")

def run():
    # Streamlit UI components
    st.title("📄 **PDF Keyword Extractor**")
    st.markdown("This tool helps you extract text from PDFs and search for specific keywords. The matched keywords will be highlighted in the text along with their surrounding context.")

    # Upload PDF file
    pdf_file = st.file_uploader("Upload PDF file", type=["pdf"])
    keywords_input = st.text_area("Enter keywords to search (comma-separated)", "")

    # Select how many surrounding sentences to show
    surrounding_sentences_count = st.slider(
        "Select the number of surrounding sentences to show:",
        min_value=1,
        max_value=5,
        value=2,
        step=1
    )

    # Add padding for a more spacious layout
    st.markdown("<br>", unsafe_allow_html=True)

    if pdf_file and keywords_input:
        keywords = [keyword.strip() for keyword in keywords_input.split(",") if keyword.strip()]
        
        if not keywords:
            st.error("Please enter at least one keyword.")
            return
        
        # Save the uploaded file to disk temporarily
        with open("temp.pdf", "wb") as f:
            f.write(pdf_file.getbuffer())

        # Extract keyword matches from text
        keyword_results = {}
        for keyword in keywords:
            keyword_results[keyword] = extract_keyword_info("temp.pdf", [keyword], surrounding_sentences_count)
        
        # Display the results
        display_results(keyword_results)

if __name__ == "__main__":
    run()
