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

# Load the SpaCy English model
nlp = spacy.load('en_core_web_md')

# Function to extract keyword information and surrounding context from PDF
def extract_keyword_info(pdf_path, keywords, surrounding_sentences_count=2):
    keywords = [keyword.lower() for keyword in keywords]  # Convert keywords to lowercase
    extracted_data = {}

    # Open the PDF file
    doc = fitz.open(pdf_path)

    # Iterate through the pages
    for page_number in range(len(doc)):
        page = doc.load_page(page_number)  # Load the page
        text = page.get_text()

        if text:
            # Process the text with SpaCy to create a document object
            doc_spacy = nlp(text)

            # Tokenize into sentences
            sentences = [sent.text for sent in doc_spacy.sents]

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

# Function to highlight keywords in a sentence
def highlight_keywords(text, keywords):
    """Highlight keywords in the sentence"""
    for keyword in keywords:
        text = re.sub(f'({re.escape(keyword)})', r'<b style="color: red;">\1</b>', text, flags=re.IGNORECASE)
    return text

# Function to highlight keywords on a PDF page
def highlight_pdf_page(pdf_path, page_number, keywords):
    """Highlight keywords in the PDF page using rectangles"""
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_number - 1)  # Page numbers are 1-based, so adjust for 0-based indexing

    # Loop through each keyword to find and highlight occurrences
    for keyword in keywords:
        text_instances = page.search_for(keyword)  # Find the keyword locations in the text

        for inst in text_instances:
            # Create a rectangle based on the text instance
            rect = fitz.Rect(inst)
            # Draw a neon green rectangle around the keyword (no fill)
            page.draw_rect(rect, color=(0, 1, 0))

    # Save the updated PDF with a unique name based on the timestamp
    timestamp = int(time.time())  # Get current timestamp
    highlighted_pdf_path = f"temp_highlighted_page_{timestamp}.pdf"
    # Check if the file already exists and try to delete it
    if os.path.exists(highlighted_pdf_path):
        try:
            os.remove(highlighted_pdf_path)  # Try to remove the file if it exists
        except PermissionError as e:
            print(f"Error: Unable to delete {highlighted_pdf_path}. {e}")

    # Save the file with a unique name
    try:
        doc.save(highlighted_pdf_path)
        print(f"Highlighted PDF saved to: {highlighted_pdf_path}")
    except Exception as e:
        print(f"Error: Unable to save PDF: {e}")

    return highlighted_pdf_path

# Function to display keyword stats in a table
def display_keyword_stats(filtered_results, keywords):
    """Display stats for keywords and the number of pages they are found on"""
    stats_data = []
    for keyword in keywords:
        pages_found = [page for page, matches in filtered_results.items() if any(keyword.lower() in match['sentence'].lower() for match in matches)]
        stats_data.append([keyword, len(pages_found), pages_found])

    # Create a DataFrame for display
    stats_df = pd.DataFrame(stats_data, columns=["Keyword", "Occurrences", "Pages"])
    st.write("### Keyword Statistics")
    st.dataframe(stats_df)

# Function to display PDF pages and highlight the keyword occurrences
def display_pdf_pages(pdf_path, pages_with_matches, keywords):
    """Display PDF pages as images with keyword highlights"""
    doc = fitz.open(pdf_path)

    # Create a dictionary to store images and their respective page numbers
    images = {}

    for i in range(len(doc)):
        # If the page has matches, highlight the page first
        if i + 1 in pages_with_matches:
            # Highlight the page and get the path of the updated PDF
            highlighted_pdf = highlight_pdf_page(pdf_path, i + 1, keywords)

            # Open the highlighted PDF page to render it as an image
            doc_highlighted = fitz.open(highlighted_pdf)
            page_highlighted = doc_highlighted.load_page(i)  # Load the page from the highlighted PDF

            # Render the page to an image (pixmap)
            pix = page_highlighted.get_pixmap(dpi=300)  # Increase DPI for higher clarity

            # Convert the pixmap image to a PIL image
            pil_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Optionally enhance the image clarity using Pillow (e.g., brightness)
            enhancer = ImageEnhance.Contrast(pil_image)
            pil_image = enhancer.enhance(1.5)  # Increase contrast by 1.5 times

            # Save the image to a BytesIO object
            img_byte_arr = BytesIO()
            pil_image.save(img_byte_arr, format="PNG")
            img_byte_arr.seek(0)  # Seek to the start of the BytesIO buffer

            # Store the image in the dictionary
            images[i + 1] = img_byte_arr
    
    return images

# Main function to run the Streamlit app
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
        
        # Filter out pages with no matches for any of the keywords
        filtered_results = {}
        for keyword, matches in keyword_results.items():
            for page, match_list in matches.items():
                if page not in filtered_results:
                    filtered_results[page] = []
                filtered_results[page].extend(match_list)

        # Display keyword stats
        display_keyword_stats(filtered_results, keywords)

        # Display the results for matched pages and keywords
        if filtered_results:
            page_images = display_pdf_pages("temp.pdf", filtered_results.keys(), keywords)
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
            st.warning("No matches found for the given keywords.")

if __name__ == "__main__":
    run()
