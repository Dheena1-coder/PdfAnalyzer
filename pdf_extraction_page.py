import fitz  # PyMuPDF
import spacy
import re
import streamlit as st
import pandas as pd  # For handling Excel conversion
import os
import time
from io import BytesIO
from PIL import Image, ImageEnhance  # Import Pillow for image processing
import tempfile
import urllib.request
import zipfile
import nltk
from nltk.tokenize import word_tokenize, sent_tokenize
nltk.download('punkt')

# Function to extract keyword information and surrounding context from PDF
def extract_keyword_info(pdf_path, keywords, surrounding_sentences_count=2):
    keywords = [keyword.lower() for keyword in keywords]  # Convert keywords to lowercase
    extracted_data = {}

    doc = fitz.open(pdf_path)

    if len(doc) == 0:
        raise ValueError("The uploaded PDF has no pages.")
    
    for page_number in range(len(doc)):
        page = doc.load_page(page_number)
        text = page.get_text()

        if text:
            sentences = sent_tokenize(text)

            matching_sentences = []
            for idx, sentence in enumerate(sentences):
                if any(keyword in sentence.lower() for keyword in keywords):
                    start_idx = max(0, idx - surrounding_sentences_count)
                    end_idx = min(len(sentences), idx + surrounding_sentences_count + 1)
                    surrounding = sentences[start_idx:end_idx]
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
    for keyword in keywords:
        text = re.sub(f'({re.escape(keyword)})', r'<b style="color: red;">\1</b>', text, flags=re.IGNORECASE)
    return text

# Load the SFDR and Asset Keyword data from GitHub (URLs directly)
def load_keywords_from_github(url):
    # Load the Excel file directly from GitHub
    df = pd.read_excel(url, engine='openpyxl')  
    return df
# Process data into dictionary
def process_keywords_to_dict(df, team_type):
    keyword_dict = {}
    for index, row in df.iterrows():
        indicator = row['SFDR Indicator'] if team_type == 'sfdr' else row['Asset Type']
        datapoint_name = row['Datapoint Name']
        keywords = row['Keywords'].split(',')
        keywords = [keyword.strip() for keyword in keywords]

        if indicator not in keyword_dict:
            keyword_dict[indicator] = {}

        if datapoint_name not in keyword_dict[indicator]:
            keyword_dict[indicator][datapoint_name] = []

        keyword_dict[indicator][datapoint_name].extend(keywords)

    # Optional: Remove duplicates within each list of keywords for each Datapoint Name
    for indicator in keyword_dict:
        for datapoint in keyword_dict[indicator]:
            keyword_dict[indicator][datapoint] = list(set(keyword_dict[indicator][datapoint]))

    return keyword_dict
# Function to display keyword stats in a table
def display_keyword_stats(filtered_results, keywords):
    stats_data = []
    for keyword in keywords:
        pages_found = [page for page, matches in filtered_results.items() if any(keyword.lower() in match['sentence'].lower() for match in matches)]
        stats_data.append([keyword, len(pages_found), pages_found])

    stats_df = pd.DataFrame(stats_data, columns=["Keyword", "Occurrences", "Pages"])
    st.write("### Keyword Statistics")
    st.dataframe(stats_df)

# Function to display PDF pages and highlight the keyword occurrences
def display_pdf_pages(pdf_path, pages_with_matches, keywords):
    doc = fitz.open(pdf_path)

    images = {}

    for i in range(len(doc)):
        if i + 1 in pages_with_matches:
            highlighted_pdf = highlight_pdf_page(pdf_path, i + 1, keywords)

            doc_highlighted = fitz.open(highlighted_pdf)
            page_highlighted = doc_highlighted.load_page(i)

            pix = page_highlighted.get_pixmap(dpi=300)
            pil_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            enhancer = ImageEnhance.Contrast(pil_image)
            pil_image = enhancer.enhance(1.5)

            img_byte_arr = BytesIO()
            pil_image.save(img_byte_arr, format="PNG")
            img_byte_arr.seek(0)

            images[i + 1] = img_byte_arr
    
    return images

# Streamlit UI
def run():
    # Streamlit UI components
    st.title("📄 **PDF Keyword Extractor & Table Extractor**")
    st.markdown("This tool helps you extract text from PDFs and search for specific keywords. The matched keywords will be highlighted in the text along with their surrounding context. Additionally, you can extract tables from specific pages and save them as Excel files.")

    # Upload PDF file
    pdf_file = st.file_uploader("Upload PDF file", type=["pdf"])    
    # URLs of the GitHub Excel files (update with actual raw GitHub links)
    sfdr_file_url = "https://raw.github.com/Dheena1-coder/PdfAnalyzer/master/sfdr_file.xlsx"  # Replace with actual SFDR Excel file URL
    asset_file_url = "https://raw.github.com/Dheena1-coder/PdfAnalyzer/master/asset_file.xlsx"  # Replace with actual Asset Excel file URL

    # Load and process the keyword dictionaries
    sfdr_df = load_keywords_from_github(sfdr_file_url)
    asset_df = load_keywords_from_github(asset_file_url)

    sfdr_keywords_dict = process_keywords_to_dict(sfdr_df, 'sfdr')
    asset_keywords_dict = process_keywords_to_dict(asset_df, 'assets')

    # Create dropdown for team selection
    team_type = st.selectbox("Select Team", ["sfdr", "physical assets"])

    # Display appropriate keyword dictionary based on team selection
    if team_type == "sfdr":
        indicators = list(sfdr_keywords_dict.keys())
    else:
        indicators = list(asset_keywords_dict.keys())
    
    indicator = st.selectbox("Select Indicator", indicators)
    if team_type == "sfdr":
        datapoint_names = list(sfdr_keywords_dict[indicator].keys())
    else:
        datapoint_names = list(asset_keywords_dict[indicator].keys())
    
    datapoint_name = st.multiselect("Select Datapoint Names", datapoint_names)
    
    # Keyword Text Area: Allow users to add additional keywords
    extra_keywords_input = st.text_area("Additional Keywords (comma-separated)", "")

    # If user submits
    if st.button("Submit"):
        # Extract relevant keywords based on the selected datapoint names
        selected_keywords = []
        if team_type == "sfdr":
            for datapoint in datapoint_name:
                selected_keywords.extend(sfdr_keywords_dict[indicator].get(datapoint, []))
        else:
            for datapoint in datapoint_name:
                selected_keywords.extend(asset_keywords_dict[indicator].get(datapoint, []))

        selected_keywords = list(set(selected_keywords))  # Remove duplicates
        
        # Add any extra keywords entered in the text area
        if extra_keywords_input:
            extra_keywords = [keyword.strip() for keyword in extra_keywords_input.split(',')]
            selected_keywords.extend(extra_keywords)

        selected_keywords = list(set(selected_keywords))  # Remove duplicates after adding extra keywords
        st.write(selected_keywords)
        # Select how many surrounding sentences to show
        surrounding_sentences_count = st.slider(
        "Select the number of surrounding sentences to show:",
        min_value=1,
        max_value=5,
        value=2,
        step=1
    )   


        if pdf_file:
            st.write("PDF file uploaded successfully.")
            with open("temp.pdf", "wb") as f:
                f.write(pdf_file.getbuffer())

            keyword_results = {}
            for keyword in selected_keywords:
                keyword_results[keyword] = extract_keyword_info("temp.pdf", [keyword],surrounding_sentences_count)

            filtered_results = {}
            for keyword, matches in keyword_results.items():
                for page, match_list in matches.items():
                    if page not in filtered_results:
                        filtered_results[page] = []
                    filtered_results[page].extend(match_list)

            # Display keyword stats
            display_keyword_stats(filtered_results, selected_keywords)

            # Display results for matched pages and keywords
            if filtered_results:
                page_images = display_pdf_pages("temp.pdf", filtered_results.keys(), selected_keywords)
                for keyword, matches in keyword_results.items():
                    with st.expander(f"Results for '{keyword}'"):
                        for page, match_list in matches.items():
                            st.markdown(f"### **Page {page}:**")
                            
                            # Display the image of the page
                            if page in page_images:
                                st.image(page_images[page], caption=f"Page {page}", use_column_width=True)

                            for match in match_list:
                                st.markdown(f"#### **Matched Sentence on Page {match['page_number']}:**")
                                st.markdown(f"<p style='color: #00C0F9;'>{match['sentence']}</p>", unsafe_allow_html=True)
                                st.write("**Context**: ")
                                for context_sentence in match['surrounding_context']:
                                    st.write(f"  - {context_sentence}")

            else:
                st.warning("No matches found for the selected keywords.")
        else:
            st.warning("Please upload a PDF file.")

if __name__ == "__main__":
    run()
