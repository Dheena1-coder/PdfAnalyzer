import streamlit as st

# Set the page configuration (optional)
st.set_page_config(page_title="Extractor", page_icon=":material/edit:")

# Sidebar for navigation
page = st.sidebar.selectbox("Select a page", ["PDF Extractor", "Web Extractor"])

# Conditional logic for different pages
if page == "PDF Extractor":
    st.title("PDF Extractor")
    # Import and run the PDF extraction page
    import pdf_extraction_page
    pdf_extraction_page.run()

elif page == "Web Extractor":
    st.title("Web Extractor")
    # Import and run the web extraction page
    import web_extraction_page
    web_extraction_page.run()
