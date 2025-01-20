import fitz  # PyMuPDF
import spacy
import re
import streamlit as st
import camelot  # For table extraction
import pandas as pd  # For handling Excel conversion
import os
import time
from io import BytesIO
from PIL import Image, ImageEnhance  # Import Pillow for image processing
import pdfplumber
import tempfile
import tabula
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
# Function to handle duplicate column names
def handle_duplicate_columns(columns):
    """Rename duplicate column names by appending a suffix (_1, _2, etc.)."""
    seen = {}
    new_columns = []
    for col in columns:
        if col in seen:
            seen[col] += 1
            new_columns.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            new_columns.append(col)
    return new_columns

import camelot
from PyPDF2 import PdfReader

def extract_table_from_pdf_with_camelot(pdf_stream, page_number):
    """Extract tables from a PDF page using Camelot."""
    try:
        # Save the BytesIO stream to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(pdf_stream.read())
            temp_file_path = temp_file.name        
        # Use Camelot to read the PDF from the BytesIO stream
        tables = camelot.read_pdf(temp_file_path, pages=str(page_number), flavor='stream', edge_tol=200, row_tol=10, split_text=False)
        
        if tables:
            # Convert tables to pandas DataFrame
            table_dfs = [table.df for table in tables]
            os.remove(temp_file_path)  # Clean up the temporary file
            return table_dfs
        else:
            os.remove(temp_file_path)  # Clean up the temporary file
            st.warning("No tables found on this page.")
            return None
    except Exception as e:
        # If an error occurs, print it and clean up any created files
        st.error(f"Error extracting tables: {e}")
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)  # Clean up the temporary file if it exists
        return None
# Function to extract table from PDF using Tabula (for structured tables)
def extract_table_from_pdf_with_tabula(pdf_stream, page_number):
    """Extract tables from a PDF page using Tabula."""
    try:
        # Save the BytesIO stream to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(pdf_stream.read())
            temp_file_path = temp_file.name

        # Use Tabula to extract tables from the specific page
        tables = tabula.read_pdf(temp_file_path, pages=page_number, multiple_tables=True, lattice=True)

        if tables:
            # Convert tables to pandas DataFrame
            table_dfs = [pd.DataFrame(table) for table in tables]
            os.remove(temp_file_path)  # Clean up the temporary file
            return table_dfs
        else:
            os.remove(temp_file_path)  # Clean up the temporary file
            st.warning("No tables found on this page.")
            return None
    except Exception as e:
        # If an error occurs, print it and clean up any created files
        st.error(f"Error extracting tables: {e}")
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)  # Clean up the temporary file if it exists
        return None

# Function to convert extracted table to Excel
def convert_table_to_excel(tables):
    """Convert pdfplumber tables to an Excel file"""
    # Create a Pandas Excel writer object
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for i, table in enumerate(tables):
            # Write each table to a sheet in Excel
            table.to_excel(writer, sheet_name=f'Table_{i + 1}', index=False)

    output.seek(0)  # Move to the beginning of the BytesIO object
    return output

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
    st.title("📄 **PDF Keyword Extractor & Table Extractor**")
    st.markdown("This tool helps you extract text from PDFs and search for specific keywords. The matched keywords will be highlighted in the text along with their surrounding context. Additionally, you can extract tables from specific pages and save them as Excel files.")

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

        pdf_stream = BytesIO(pdf_file.read())  # Convert bytes to a BytesIO stream for Camelot

        # Add dropdown for table extraction type (structured vs unstructured)
        table_type = st.selectbox("Choose table type", ("Structured Table", "Unstructured Table"))

        # Prompt the user for a page number to extract the table from
        page_number = st.number_input("Enter the page number to extract the table from:", min_value=1)

        if page_number:
            # Extract the table based on selected type
            if table_type == "Structured Table":
                # Use the function for structured table extraction
                tables = extract_table_from_pdf_with_tabula(pdf_stream, page_number)
            else:
                # Use the function for unstructured table extraction
                tables = extract_table_from_pdf_with_camelot(pdf_stream, page_number)

            if tables:
                st.write(f"Extracted Tables from Page {page_number}:")
                for i, table in enumerate(tables):
                    st.write(f"**Table {i + 1}:**")
                    st.dataframe(table)

                # Allow the user to download the table as an Excel file
                excel_output = convert_table_to_excel(tables)
                st.download_button(
                    label="Download Table as Excel",
                    data=excel_output,
                    file_name=f"table_page_{page_number}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.write("No tables found on the selected page.")
if __name__ == "__main__":
    run()
