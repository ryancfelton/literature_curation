import streamlit as st
import arxiv
import requests
import re
import html
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from xml.etree import ElementTree as ET

st.set_page_config(page_title="Literature Curation Tool", layout="wide")

st.title("🌌 Planetary Sciences and Astrobiology AI/ML Literature Curation")
st.markdown("Curate publications in planetary sciences and astrobiology that utilize AI/ML approaches.")

# Sidebar Configuration
st.sidebar.header("Search & Source Settings")

# 1. Source Toggle
data_source = st.sidebar.radio(
    "Select Data Source", 
    ["arXiv (astro-ph.EP)", "Harvard ADS (astro-ph.EP)", "Astrobiology (Journal Only)"]
)

ads_api_key = ""
if data_source in ["Harvard ADS (astro-ph.EP)", "Astrobiology (Journal Only)"]:
    if "ADS_API_KEY" in st.secrets and st.secrets["ADS_API_KEY"]:
        ads_api_key = st.secrets["ADS_API_KEY"]
    else:
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

def clean_text(text):
    """Removes raw XML/MathML tags (common in ADS) and unescapes HTML entities."""
    if not isinstance(text, str):
        return "N/A"
    text = html.unescape(text)
    text = re.sub(r'<[a-zA-Z\/][^>]*>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def format_ads_date(pubdate_str, year):
    """Formats ADS YYYY-MM-DD dates, cleanly resolving '00' placeholders for missing days/months."""
    if not pubdate_str or pubdate_str == "N/A":
        return str(year)
    
    parts = pubdate_str.split('-')
    if len(parts) == 3:
        y, m, d = parts
        months = ["", "January", "February", "March", "April", "May", "June", 
                  "July", "August", "September", "October", "November", "December"]
        try:
            m_int = int(m)
            d_int = int(d)
            if m_int > 0 and d_int > 0:
                dt = datetime(int(y), m_int, d_int)
                return dt.strftime("%B %d, %Y")
            elif m_int > 0:
                return f"{months[m_int]} {y}"
            else:
                return str(y)
        except ValueError:
            return pubdate_str
    return pubdate_str

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
        "clustering": "Clustering",
        "artificial intelligence": "AI",
        "decision tree": "Decision Trees",
        "xgboost": "XGBoost"
    }
    found = []
    text = abstract.lower() if abstract else ""
    for pattern, name in ai_keywords.items():
        if pattern in text and name not in found:
            found.append(name)
        if len(found) >= 4:
            break
            
    return list(dict.fromkeys(found))

def fetch_arxiv_data(years, limit_per_year):
    client = arxiv.Client()
    ai_terms = '(ti:"machine learning" OR ab:"machine learning" OR ti:"neural network" OR ab:"neural network" OR ti:"deep learning" OR ab:"deep learning" OR ti:"artificial intelligence" OR ab:"artificial intelligence")'
    
    all_papers = []
    for year in years:
        date_query = f'submittedDate:[{year}01010000 TO {year}12312359]'
        query = f'cat:astro-ph.EP AND {date_query} AND {ai_terms}'
        
        search = arxiv.Search(
            query=query,
            max_results=limit_per_year * 5,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )
        
        count = 0
        for result in client.results(search):
            clean_summary = clean_text(result.summary)
            clean_title = clean_text(result.title)
            keywords = extract_keywords(clean_summary)
            
            if keywords:
                paper_data = {
                    "title": clean_title,
                    "authors": [a.name for a in result.authors],
                    "year": result.published.year,
                    "published_date": result.published.strftime("%B %d, %Y"),
                    "summary": clean_summary,
                    "arxiv_id": result.entry_id.split("/")[-1],
                    "bibcode": "N/A",
                    "ads_url": "N/A",
                    "pdf_url": result.pdf_url,
                    "doi": result.doi if result.doi else "N/A",
                    "keywords": keywords,
                    "source": "arXiv"
                }
                all_papers.append(paper_data)
                count += 1
                
            if count >= limit_per_year:
                break
                
    return all_papers

def fetch_ads_data(api_key, years, limit_per_year, source_type):
    if not api_key:
        st.error("Please enter a valid Harvard ADS API Token or set ADS_API_KEY in Streamlit Secrets.")
        return []
    
    all_papers = []
    headers = {"Authorization": f"Bearer {api_key}"}
    
    for year in years:
        ai_terms = 'abs:("machine learning" OR "deep learning" OR "neural network" OR "artificial intelligence")'
        
        if source_type == "Harvard ADS (astro-ph.EP)":
            cat_terms = '(arxiv_class:"astro-ph.EP" OR keyword:"astro-ph.EP" OR abs:"astro-ph.EP")'
        else:
            # Strictly the Mary Ann Liebert Astrobiology journal (Bibstem: AsBio)
            cat_terms = 'bibstem:"AsBio"'
            
        query = f'{ai_terms} AND {cat_terms} AND year:{year}'
        
        params = {
            "q": query,
            "fl": "title,author,year,pubdate,abstract,identifier,doi,bibcode",
            "rows": limit_per_year * 5,
            "sort": "date desc"
        }
        res = requests.get("https://api.adsabs.harvard.edu/v1/search/query", headers=headers, params=params)
        
        if res.status_code == 200:
            docs = res.json().get("response", {}).get("docs", [])
            count = 0
            
            for doc in docs:
                raw_abstract = doc.get("abstract", "No abstract available.")
                clean_abstract = clean_text(raw_abstract)
                keywords = extract_keywords(clean_abstract)
                
                if keywords:
                    raw_title = doc.get("title", ["N/A"])[0] if doc.get("title") else "N/A"
                    clean_title = clean_text(raw_title)
                    authors = doc.get("author", ["N/A"])
                    bibcode = doc.get("bibcode", "N/A")
                    
                    raw_pubdate = doc.get("pubdate", str(year))
                    formatted_date = format_ads_date(raw_pubdate, year)
                    
                    arxiv_id = "N/A"
                    for ident in doc.get("identifier", []):
                        if "arXiv:" in ident or "arxiv:" in ident:
                            arxiv_id = ident.replace("arXiv:", "").replace("arxiv:", "")
                            break
                            
                    doi = doc.get("doi", ["N/A"])[0] if doc.get("doi") else "N/A"
                    ads_url = f"https://ui.adsabs.harvard.edu/abs/{bibcode}/abstract" if bibcode != "N/A" else "N/A"
                    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id != "N/A" else ads_url
                    
                    all_papers.append({
                        "title": clean_title,
                        "authors": authors,
                        "year": int(doc.get("year", year)),
                        "published_date": formatted_date,
                        "summary": clean_abstract,
                        "arxiv_id": arxiv_id,
                        "bibcode": bibcode,
                        "ads_url": ads_url,
                        "pdf_url": pdf_url,
                        "doi": doi,
                        "keywords": keywords,
                        "source": source_type
                    })
                    count += 1
                    
                if count >= limit_per_year:
                    break
        else:
            st.error(f"ADS API Error for year {year}: {res.status_code}")
            
    return all_papers

def generate_pdf(papers, source_name):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, leading=20)
    normal_style = styles['Normal']
    
    story.append(Paragraph(f"Curated {source_name} AI/ML Literature", title_style))
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
        
        if "arXiv" in paper['source']:
            ref_line = f"arXiv:{paper['arxiv_id']} | Link: {paper['pdf_url']}"
        else:
            ref_line = f"Bibcode: {paper['bibcode']} | Link: {paper['ads_url']}"
            
        text = f"<b>Title:</b> {paper['title']}<br/>" \
               f"<b>Authors:</b> {authors}<br/>" \
               f"<b>AI/ML Keywords:</b> {kw_str}<br/>" \
               f"<b>Reference:</b> {ref_line} | DOI: {paper['doi']}<br/>"
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
        ET.SubElement(pub, "source").text = p["source"]
        
        ref = ET.SubElement(pub, "reference")
        ET.SubElement(ref, "bibcode").text = p["bibcode"]
        ET.SubElement(ref, "ads_url").text = p["ads_url"]
        ET.SubElement(ref, "arxiv_id").text = p["arxiv_id"]
        ET.SubElement(ref, "pdf_url").text = p["pdf_url"]
        ET.SubElement(ref, "doi").text = p["doi"]
        
    return ET.tostring(root, encoding="utf-8", method="xml")

if st.button(f"Fetch & Curate Literature from {data_source.split(' ')[0]}"):
    with st.spinner(f"Querying {data_source} for up to {papers_per_year} papers/year..."):
        if data_source == "arXiv (astro-ph.EP)":
            papers = fetch_arxiv_data(selected_years, papers_per_year)
        else:
            papers = fetch_ads_data(ads_api_key, selected_years, papers_per_year, data_source)
            
        st.session_state['papers'] = papers
        st.session_state['current_source'] = data_source

if 'papers' in st.session_state:
    papers = st.session_state['papers']
    current_source = st.session_state.get('current_source', data_source)
    
    if len(papers) == 0:
        st.info(f"No publications utilizing AI/ML approaches were found in {current_source} for the selected parameters.")
    else:
        st.subheader(f"Curated Publications ({len(papers)} Total Fetched from {current_source})")
        
        search_query = st.text_input("🔍 Search within fetched results...", "")
        
        filtered_papers = []
        if search_query:
            query_lower = search_query.lower()
            for p in papers:
                if (query_lower in p['title'].lower() or 
                    query_lower in p['summary'].lower() or 
                    any(query_lower in author.lower() for author in p['authors']) or 
                    any(query_lower in kw.lower() for kw in p['keywords'])):
                    filtered_papers.append(p)
        else:
            filtered_papers = papers

        if len(filtered_papers) == 0:
            st.warning("No fetched papers match your search query.")
        else:
            if search_query:
                st.write(f"**Showing {len(filtered_papers)} results matching '{search_query}'**")
                
            curr_yr = None
            for p in filtered_papers:
                if p['year'] != curr_yr:
                    curr_yr = p['year']
                    st.markdown(f"--- \n### Year: {curr_yr}")
                    
                with st.expander(f"**{p['title']}** ({p['published_date']})"):
                    st.markdown(f"**Authors:** {', '.join(p['authors'])}")
                    st.markdown(f"**AI/ML Methods Used:** `{', '.join(p['keywords'])}`")
                    st.markdown(f"**Abstract:** {p['summary']}")
                    
                    if "arXiv" in p['source']:
                        st.markdown(f"**Reference Info:** arXiv:{p['arxiv_id']} | DOI: {p['doi']} | [PDF Link]({p['pdf_url']})")
                    else:
                        st.markdown(f"**Reference Info:** Bibcode: [`{p['bibcode']}`]({p['ads_url']}) | DOI: {p['doi']} | arXiv:{p['arxiv_id']}")

        if len(filtered_papers) > 0:
            st.sidebar.header("Download Options")
            
            pdf_data = generate_pdf(filtered_papers, current_source)
            st.sidebar.download_button(
                label="📄 Download PDF",
                data=pdf_data,
                file_name=f"{current_source.split(' ')[0].lower()}_curated_literature.pdf",
                mime="application/pdf"
            )
            
            xml_data = generate_xml(filtered_papers)
            st.sidebar.download_button(
                label="🏷️ Download XML",
                data=xml_data,
                file_name=f"{current_source.split(' ')[0].lower()}_curated_literature.xml",
                mime="application/xml"
            )
