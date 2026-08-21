import streamlit as st
import arxiv
import requests
import re
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from xml.etree import ElementTree as ET

st.set_page_config(page_title="Literature Curation Tool", layout="wide")

st.title("🌌 Earth & Planetary Astrophysics AI/ML Literature Curation")
st.markdown("Curate publications in `astro-ph.EP` that utilize AI/ML approaches.")

# Sidebar Configuration
st.sidebar.header("Search & Source Settings")

# 1. Source Toggle
data_source = st.sidebar.radio("Select Data Source", ["arXiv", "Harvard ADS"])

ads_api_key = ""
if data_source == "Harvard ADS":
    ads_api_key = st.sidebar.text_input("Harvard ADS API Token", type="password", help="Get your free API key at ui.adsabs.harvard.edu")

# 2. Year Filter Slider
current_year = 2026
year_range = st.sidebar.slider(
    "Publication Years",
    min_value=2010,
    max_value=current_year,
    value=(2023, current_year),
    step=1
)
selected_years = list(range(year_range[1], year_range[0] - 1, -1)) # Reverse chronological

# 3. Papers Per Year Limit Slider
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
    text = abstract.lower() if abstract else ""
    for pattern, name in ai_keywords.items():
        if pattern in text and name not in found:
            found.append(name)
        if len(found) >= 4:
            break
    if len(found) < 2:
        found.extend(["Machine Learning", "Data Science"])
    return list(dict.fromkeys(found))[:4]

def fetch_arxiv_data(years, limit_per_year):
    client = arxiv.Client()
    ai_terms = '(ti:"machine learning" OR ab:"machine learning" OR ti:"neural network" OR ab:"neural network" OR ti:"deep learning" OR ab:"deep learning" OR ti:"artificial intelligence" OR ab:"artificial intelligence")'
    
    all_papers = []
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

def fetch_ads_data(api_key, years, limit_per_year):
    if not api_key:
        st.error("Please enter a valid Harvard ADS API Token in the sidebar.")
        return []
    
    all_papers = []
    headers = {"Authorization": f"Bearer {api_key}"}
    ai_terms = 'abs:("machine learning" OR "deep learning" OR "neural network" OR "artificial intelligence")'
    
    for year in years:
        query = f'{ai_terms} AND year:{year} AND (keyword:"astro-ph.EP" OR abs:"astro-ph.EP" OR doctype:"eprint")'
        params = {
            "q": query,
            "fl": "title,author,year,pubdate,abstract,identifier,doi,bibcode",
            "rows": limit_per_year,
            "sort": "date desc"
        }
        res = requests.get("https://api.adsabs.harvard.edu/v1/search/query", headers=headers, params=params)
        if res.status_code == 200:
            docs = res.json().get("response", {}).get("docs", [])
            for doc in docs:
                title = doc.get("title", ["N/A"])[0] if doc.get("title") else "N/A"
                authors = doc.get("author", ["N/A"])
                abstract = doc.get("abstract", "No abstract available.")
                arxiv_id = "N/A"
                for ident in doc.get("identifier", []):
                    if "arXiv:" in ident or "arxiv:" in ident:
                        arxiv_id = ident.replace("arXiv:", "").replace("arxiv:", "")
                        break
                doi = doc.get("doi", ["N/A"])[0] if doc.get("doi") else "N/A"
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id != "N/A" else f"https://ui.adsabs.harvard.edu/abs/{doc.get('bibcode', '')}/abstract"
                
                all_papers.append({
                    "title": title,
                    "authors": authors,
                    "year": int(doc.get("year", year)),
                    "published_date": doc.get("pubdate", str(year)),
                    "summary": abstract,
                    "arxiv_id": arxiv_id,
                    "pdf_url": pdf_url,
                    "doi": doi,
                    "journal_ref": doc.get("bibcode", "N/A"),
                    "keywords": extract_keywords(abstract)
                })
        else:
            st.error(f"ADS API Error for year {year}: {res.status_code}")
    return all_papers

def generate_pdf(papers):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, leading=20)
    normal_style = styles['Normal']
    
    story.append(Paragraph(f"Curated {data_source} AI/ML Literature (astro-ph.EP)", title_style))
    story.append(Spacer(1, 12))
    
    curr_yr = None
    for paper in papers:
        if paper['year'] != curr_yr:
            curr_yr = paper['year']
            story.append(Spacer(1, 10))
            story.append(Paragraph(f"<b>--- Publication Year: {curr_yr} ---</b>", styles['Heading2']))
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

if st.button(f"Fetch & Curate Literature from {data_source}"):
    with st.spinner(f"Fetching up to {papers_per_year} papers/year across {len(selected_years)} years..."):
        if data_source == "arXiv":
            papers = fetch_arxiv_data(selected_years, papers_per_year)
        else:
            papers = fetch_ads_data(ads_api_key, selected_years, papers_per_year)
            
        st.session_state['papers'] = papers

if 'papers' in st.session_state and st.session_state['papers']:
    papers = st.session_state['papers']
    
    st.subheader(f"Curated Publications ({len(papers)} Total Returned)")
    
    curr_yr = None
    for p in papers:
        if p['year'] != curr_yr:
            curr_yr = p['year']
            st.markdown(f"--- \n### 📅 Year: {curr_yr}")
            
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
        file_name="curated_literature.pdf",
        mime="application/pdf"
    )
    
    xml_data = generate_xml(papers)
    st.sidebar.download_button(
        label="🏷️ Download XML",
        data=xml_data,
        file_name="curated_literature.xml",
        mime="application/xml"
    )
