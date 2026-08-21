import streamlit as st
import arxiv
import re
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from xml.etree import ElementTree as ET

st.set_page_config(page_title="arXiv Literature Curation", layout="wide")

st.title("🌌 Earth & Planetary Astrophysics AI/ML Literature Curation")
st.markdown("Curated papers from `astro-ph.EP` utilizing AI/ML approaches (2023–2026).")

# Sidebar settings
st.sidebar.header("Search Configuration")
papers_per_year = st.sidebar.slider(
    "Publications per year",
    min_value=1,
    max_value=100,
    value=10,
    step=1
)

def extract_keywords(abstract):
    ai_keywords = {
        "machine learning": "Machine Learning",
        "deep learning": "Deep Learning",
        "neural network": "Neural Networks",
        "convolutional": "CNNs",
        "random forest": "Random Forest",
        "gaussian process": "Gaussian Processes",
        "support vector": "SVM",
        "reinforcement learning": "Reinforcement Learning",
        "transformer": "Transformers",
        "autoencoder": "Autoencoders",
        "surrogate": "Surrogate Modeling",
        "physics-informed": "PINNs",
        "classification": "AI Classification",
        "clustering": "Clustering"
    }
    found = []
    text = abstract.lower()
    for pattern, name in ai_keywords.items():
        if pattern in text and name not in found:
            found.append(name)
        if len(found) >= 4:
            break
    if len(found) < 2:
        found.extend(["Machine Learning", "Data Science"])
    return list(dict.fromkeys(found))[:4]

def fetch_arxiv_data(limit_per_year):
    client = arxiv.Client()
    ai_terms = '(ti:"machine learning" OR ab:"machine learning" OR ti:"neural network" OR ab:"neural network" OR ti:"deep learning" OR ab:"deep learning" OR ti:"artificial intelligence" OR ab:"artificial intelligence")'
    
    all_papers = []
    years = [2026, 2025, 2024, 2023]
    
    for year in years:
        date_query = f'submittedDate:[{year}01010000 TO {year}12312359]'
        query = f'cat:astro-ph.EP AND {date_query} AND {ai_terms}'
        
        search = arxiv.Search(
            query=query,
            max_results=limit_per_year * 2,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )
        
        count = 0
        for result in client.results(search):
            keywords = extract_keywords(result.summary)
            
            paper_data = {
                "title": result.title.replace("\n", " "),
                "authors": [a.name for a in result.authors],
                "year": result.published.year,
                "published_date": result.published.strftime("%B %d, %Y"),
                "summary": result.summary.replace("\n", " "),
                "arxiv_id": result.entry_id.split("/")[-1],
                "pdf_url": result.pdf_url,
                "doi": result.doi if result.doi else "N/A",
                "journal_ref": result.journal_ref if result.journal_ref else "N/A",
                "keywords": keywords
            }
            all_papers.append(paper_data)
            count += 1
            if count >= limit_per_year:
                break
                
    return all_papers

def generate_pdf(papers):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, leading=20)
    normal_style = styles['Normal']
    
    story.append(Paragraph("Curated arXiv AI/ML Literature (astro-ph.EP)", title_style))
    story.append(Spacer(1, 12))
    
    current_year = None
    for paper in papers:
        if paper['year'] != current_year:
            current_year = paper['year']
            story.append(Spacer(1, 10))
            story.append(Paragraph(f"<b>--- Publication Year: {current_year} ---</b>", styles['Heading2']))
            story.append(Spacer(1, 8))
            
        authors = ", ".join(paper['authors'][:3]) + (" et al." if len(paper['authors']) > 3 else "")
        kw_str = ", ".join(paper['keywords'])
        
        text = f"<b>Title:</b> {paper['title']}<br/>" \
               f"<b>Authors:</b> {authors}<br/>" \
               f"<b>AI/ML Keywords:</b> {kw_str}<br/>" \
               f"<b>Reference:</b> arXiv:{paper['arxiv_id']} | DOI: {paper['doi']} | Link: {paper['pdf_url']}<br/>"
        story.append(Paragraph(text, normal_style))
        story.append(Spacer(1, 10))
        
    doc.build(story)
    buffer.seek(0)
    return buffer

def generate_xml(papers):
    root = ET.Element("publications")
    for p in papers:
        pub = ET.SubElement(root, "publication")
        ET.SubElement(pub, "title").text = p["title"]
        ET.SubElement(pub, "year").text = str(p["year"])
        ET.SubElement(pub, "authors").text = ", ".join(p["authors"])
        ET.SubElement(pub, "keywords").text = ", ".join(p["keywords"])
        
        ref = ET.SubElement(pub, "reference")
        ET.SubElement(ref, "arxiv_id").text = p["arxiv_id"]
        ET.SubElement(ref, "pdf_url").text = p["pdf_url"]
        ET.SubElement(ref, "doi").text = p["doi"]
        ET.SubElement(ref, "journal_ref").text = p["journal_ref"]
        
    return ET.tostring(root, encoding="utf-8", method="xml")

if st.button("Fetch & Curate arXiv Literature"):
    with st.spinner(f"Fetching up to {papers_per_year} papers per year (2026 down to 2023)..."):
        papers = fetch_arxiv_data(papers_per_year)
        st.session_state['papers'] = papers

if 'papers' in st.session_state and st.session_state['papers']:
    papers = st.session_state['papers']
    
    st.subheader(f"Curated Publications ({len(papers)} Total Returned)")
    
    current_year = None
    for p in papers:
        if p['year'] != current_year:
            current_year = p['year']
            st.markdown(f"--- \n### 📅 Year: {current_year}")
            
        with st.expander(f"**{p['title']}** ({p['published_date']})"):
            st.markdown(f"**Authors:** {', '.join(p['authors'])}")
            st.markdown(f"**AI/ML Methods Used:** `{', '.join(p['keywords'])}`")
            st.markdown(f"**Abstract:** {p['summary']}")
            st.markdown(f"**Reference Info:** arXiv:{p['arxiv_id']} | DOI: {p['doi']} | [PDF Link]({p['pdf_url']})")

    st.sidebar.header("Download Options")
    
    pdf_data = generate_pdf(papers)
    st.sidebar.download_button(
        label="📄 Download PDF",
        data=pdf_data,
        file_name="arxiv_curated_literature.pdf",
        mime="application/pdf"
    )
    
    xml_data = generate_xml(papers)
    st.sidebar.download_button(
        label="🏷️ Download XML",
        data=xml_data,
        file_name="arxiv_curated_literature.xml",
        mime="application/xml"
    )
