import requests
from bs4 import BeautifulSoup
import streamlit as st
import re
import os

# Disable SSL warnings (for skipping certificate verification)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Step 1: Download the HTML content from the webpage
def get_html_content(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()  # Check if the request was successful
        
        return response.text
    except requests.exceptions.RequestException as e:
        st.error(f"Error downloading the HTML content: {e}")
        return None

# Step 2: Extract PDF link from SVG with class "c0169"
def extract_pdf_from_svg(html_content, base_url):
    # Parse HTML content
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find the <svg> element with <path> having class="c0169"
    svg_path = soup.find('svg')
    
    if svg_path:
        path = svg_path.find('path', class_='c0169')
        
        if path and path.get('d'):
            # The 'd' attribute contains the data, but we'll need to extract the actual link
            d_value = path.get('d')
            
            # Now we'll check if the d value contains a link to the PDF (this can vary)
            # For this example, we assume it's part of a URL (you may need to adjust this logic)
            match = re.search(r'(https?://[^\s]+\.pdf)', d_value)
            if match:
                pdf_url = match.group(1)
                
                # If it's a relative URL, we need to resolve it to the full URL
                if not pdf_url.startswith('http'):
                    pdf_url = os.path.join(base_url, pdf_url)
                
                return pdf_url
    
    return None

# Step 3: Download PDF if link is found
def download_pdf(pdf_url):
    try:
        # Send a GET request to download the PDF
        pdf_response = requests.get(pdf_url, stream=True)
        pdf_response.raise_for_status()  # Check if the request was successful
        
        # Get the filename from the URL
        pdf_filename = pdf_url.split('/')[-1]
        
        # Save the PDF locally
        with open(pdf_filename, 'wb') as f:
            for chunk in pdf_response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        st.success(f"PDF downloaded successfully: {pdf_filename}")
    
    except requests.exceptions.RequestException as e:
        st.error(f"Error downloading PDF: {e}")

# Step 4: Extract the text content and identify sentences containing the keyword
def extract_keyword_sentences(html_content, keywords, sentence_count=2):
    """
    Extract sentences containing the keywords and surrounding context.

    Args:
    - html_content: The HTML content of the page as a string.
    - keywords: A list of keywords to search for.
    - sentence_count: Number of surrounding sentences to include.

    Returns:
    - A dictionary with keywords as keys and list of sentence contexts as values.
    """
    # Parse HTML content and get the text
    soup = BeautifulSoup(html_content, 'html.parser')
    body_text = soup.get_text()

    keyword_sentences = {}

    # Iterate over each keyword
    for keyword in keywords:
        keyword_pattern = re.compile(r'([^.]*\b' + re.escape(keyword) + r'\b[^.!?]*[.!?])', re.IGNORECASE)
        
        # Find all sentences containing the keyword
        matched_sentences = re.findall(keyword_pattern, body_text)
        
        # Add the matched sentences to the dictionary
        keyword_sentences[keyword] = matched_sentences[:sentence_count]  # Limit by sentence_count

    return keyword_sentences

# Streamlit app to display the webpage content and extracted sentences
def run():
    st.title("Webpage Keyword Sentence Extractor")
    st.markdown(""" 
    This tool extracts sentences containing your specified keywords from a webpage and displays them interactively.
    You can click to see the full content with highlighted keywords.
    """)
    
    # Step 1: User Input for Document ID
    document_id = st.text_input("Enter Document ID:", "")
    
    # Step 2: User Input for Keywords
    keywords_input = st.text_input("Enter Keywords to Search (separated by commas):", "")
    keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
    
    # Step 3: User Input for Sentence Count (only applicable for sentence context)
    sentence_count = st.number_input("Enter Number of Sentences around the keyword:", min_value=1, max_value=5, value=2)
    
    # Step 4: Process the content if both Document ID and Keywords are provided
    if document_id and keywords:
        url = f"https://documents.msciapps.com/documents/content/data/{document_id}"
        
        # Step 5: Get the HTML content of the page
        html_content = get_html_content(url)
        if not html_content:
            st.error("Failed to get HTML content.")
            return
        
        # Step 6: Extract PDF link if present
        pdf_url = extract_pdf_from_svg(html_content, url)
        
        if pdf_url:
            # If a PDF URL is found, download it
            download_pdf(pdf_url)
        
        # Step 7: Extract the matched sentences for the keywords
        keyword_sentences = extract_keyword_sentences(html_content, keywords, sentence_count)
        
        # Step 8: Display the matched keywords and their context before the full page
        st.markdown("### Matched Keywords and Their Contexts:")

        # Loop through each keyword and show its context
        for keyword in keywords:
            st.markdown(f"#### Matches for keyword: **{keyword}**")
            
            # Extract context sentences for each keyword
            context_matches = keyword_sentences.get(keyword, [])
            
            if context_matches:
                with st.expander(f"Click to see matches for '{keyword}'"):
                    # Display the keyword context sentences in a dropdown style
                    selected_match = st.selectbox(f"Select a match for '{keyword}':", context_matches)
                    st.markdown(f"**Context around the keyword**: {selected_match}")
            else:
                st.warning(f"No matches found for the keyword '{keyword}'.")
        
        # Step 9: Optionally, Display the full page content with highlighted keywords
        st.markdown("### Full Page Content with Highlighted Keywords")

        # Highlight the keywords in the full HTML content
        for keyword in keywords:
            # Define the keyword pattern for highlighting
            keyword_pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            html_content = re.sub(keyword_pattern, lambda match: f"<span style='background-color: yellow; color: black;'>{match.group(0)}</span>", html_content)
        
        # Display the full content with highlighted keywords
        st.markdown(html_content, unsafe_allow_html=True)
        
    else:
        st.info("Please enter a Document ID and Keywords to fetch content.")

if __name__ == "__main__":
    run()
