import streamlit as st
import arxiv
import datetime
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom
import io

# Optional ReportLab import for PDF generation
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# ==========================================
# HELPER FUNCTIONS & AI/ML KEYWORD EXTRACTOR
# ==========================================

AI_ML_KEYWORDS_POOL = [
    "Machine Learning", "Deep Learning", "Neural Network", "Convolutional Neural Network (CNN)",
    "Random Forest", "Transformer", "Generative AI", "Large Language Model (LLM)",
    "Surrogate Model", "Gaussian Process", "Support Vector Machine (SVM)", "Reinforcement Learning",
    "Autoencoder", "Graph Neural Network (GNN)", "Bayesian Inference", "Clustering",
    "Decision Tree", "Supervised Learning", "Unsupervised Learning", "Physics-Informed Neural Network (PINN)"
]

def extract_aiml_keywords(abstract, max_keywords=4):
    """
    Extracts 2 to 4 relevant AI/ML keywords based on abstract text matching.
    """
    found_keywords = []
    abstract_lower = abstract.lower()
    
    # Priority term matching
    patterns = {
        "Neural Network": r"\bneural network[s]?\b|\bann\b|\bmlp\b",
        "Deep Learning": r"\bdeep learning\b|\bdeep neural\b",
        "Convolutional Neural Network (CNN)": r"\bcnn[s]?\b|\bconvolutional\b",
        "Random Forest": r"\brandom forest[s]?\b",
        "Transformer": r"\btransformer[s]?\b|\battention mechanism\b",
        "Surrogate Model": r"\bsurrogate[s]?\b|\bemulator[s]?\b",
        "Gaussian Process": r"\bgaussian process[es]?\b|\bgp regression\b",
        "Machine Learning": r"\bmachine learning\b|\bml\b",
        "Reinforcement Learning": r"\breinforcement learning\b|\brl\b",
        "Autoencoder": r"\bautoencoder[s]?\b",
        "Graph Neural Network (GNN)": r"\bgnn[s]?\b|\bgraph neural\b",
        "Bayesian Inference": r"\bbayesian\b",
        "Clustering": r"\bclustering\b|\bk-means\b|\bhdbscan\b",
        "Decision Tree": r"\bdecision tree[s]?\b",
        "Physics-Informed Neural Network (PINN)": r"\bpinn[s]?\b|\bphysics-informed\b"
    }

    for label, pattern in patterns.items():
        if re.search(pattern, abstract_lower):
            found_keywords.append(label)
            if len(found_keywords) >= max_keywords:
                break
                
    # Fallback to general terms if fewer than 2 matched
    if len(found_keywords) < 2:
        if "Machine Learning" not in found_keywords:
            found_keywords.append("Machine Learning")
        if "Data-Driven Modeling" not in found_keywords and len(found_keywords) < 2:
            found_keywords.append("Data-Driven Modeling")
            
    return found_keywords[:4]


def fetch_arxiv_planetary_aiml(target_years=[2026, 2025, 2024, 2023], max_per_year=10):
    """
    Queries arXiv API for Earth and Planetary Astrophysics (astro-ph.EP) articles that use AI/ML.
    Returns publications structured by year in reverse chronological order.
    """
    client = arxiv.Client()
    
    # Target query for astro-ph.EP category with AI/ML terms in abstract/title
    aiml_query_terms = (
        'cat:astro-ph.EP AND ('
        'abs:"machine learning" OR abs:"deep learning" OR abs:"neural network" OR '
        'abs:"random forest" OR abs:"convolutional" OR abs:"transformer" OR '
        'abs:"artificial intelligence" OR abs:"surrogate model" OR abs:"gaussian process"'
        ')'
    )
    
    # We fetch enough candidates to filter accurately by year
    search = arxiv.Search(
        query=aiml_query_terms,
        max_results=max_per_year * len(target_years) * 3,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )
    
    results_by_year = {year: [] for year in target_years}
    
    try:
        results = list(client.results(search))
    except Exception as e:
        st.error(f"Error communicating with arXiv API: {e}")
        return results_by_year

    for paper in results:
        pub_year = paper.published.year
        if pub_year in results_by_year and len(results_by_year[pub_year]) < max_per_year:
            # Extract keywords
            extracted_keywords = extract_aiml_keywords(paper.summary)
            
            # Format authors list
            authors_list = [author.name for author in paper.authors]
            authors_str = ", ".join(authors_list[:3]) + (" et al." if len(authors_list) > 3 else "")
            
            # Format reference details
            arxiv_id = paper.get_short_id()
            doi_ref = paper.doi if paper.doi else "N/A"
            journal_ref = paper.journal_ref if paper.journal_ref else "arXiv Preprint"
            
            pub_data = {
                "title": paper.title.replace("\n", " ").strip(),
                "authors": authors_str,
                "all_authors": authors_list,
                "year": pub_year,
                "published_date": paper.published.strftime("%Y-%m-%d"),
                "abstract": paper.summary.replace("\n", " ").strip(),
                "arxiv_id": arxiv_id,
                "arxiv_url": paper.entry_id,
                "pdf_url": paper.pdf_url,
                "doi": doi_ref,
                "journal_ref": journal_ref,
                "aiml_keywords": extracted_keywords
            }
            results_by_year[pub_year].append(pub_data)

    return results_by_year


# ==========================================
# EXPORT GENERATORS (XML & PDF)
# ==========================================

def generate_xml_output(curated_data):
    """Generates a clean XML structure of the curated publications."""
    root = ET.Element("CuratedLiterature", category="Earth and Planetary Astrophysics", domain="AI/ML")
    
    for year in sorted(curated_data.keys(), reverse=True):
        year_elem = ET.SubElement(root, "YearGroup", year=str(year))
        for item in curated_data[year]:
            pub_elem = ET.SubElement(year_elem, "Publication")
            ET.SubElement(pub_elem, "Title").text = item["title"]
            ET.SubElement(pub_elem, "Authors").text = item["authors"]
            ET.SubElement(pub_elem, "PublicationDate").text = item["published_date"]
            
            keywords_elem = ET.SubElement(pub_elem, "AIML_Keywords")
            for kw in item["aiml_keywords"]:
                ET.SubElement(keywords_elem, "Keyword").text = kw
                
            ET.SubElement(pub_elem, "Abstract").text = item["abstract"]
            
            ref_elem = ET.SubElement(pub_elem, "ReferenceInformation")
            ET.SubElement(ref_elem, "arXivID").text = item["arxiv_id"]
            ET.SubElement(ref_elem, "arXivURL").text = item["arxiv_url"]
            ET.SubElement(ref_elem, "PDFURL").text = item["pdf_url"]
            ET.SubElement(ref_elem, "DOI").text = item["doi"]
            ET.SubElement(ref_elem, "JournalReference").text = item["journal_ref"]
            
    xml_str = ET.tostring(root, encoding="utf-8")
    parsed_xml = minidom.parseString(xml_str)
    return parsed_xml.toprettyxml(indent="  ")


def generate_pdf_output(curated_data):
    """Generates a formatted PDF document of the curated publications."""
    if not REPORTLAB_AVAILABLE:
        return None
        
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=18, leading=22, textColor=colors.HexColor('#1E3A8A'))
    year_style = ParagraphStyle('YearHeader', parent=styles['Heading2'], fontSize=15, leading=18, textColor=colors.HexColor('#0F766E'), spaceBefore=12, spaceAfter=6)
    pub_title_style = ParagraphStyle('PubTitle', parent=styles['Heading3'], fontSize=11, leading=14, textColor=colors.HexColor('#1F2937'), spaceAfter=3)
    meta_style = ParagraphStyle('PubMeta', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.HexColor('#4B5563'))
    kw_style = ParagraphStyle('PubKW', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.HexColor('#2563EB'))
    ref_style = ParagraphStyle('PubRef', parent=styles['Italic'], fontSize=8.5, leading=11, textColor=colors.HexColor('#374151'))
    
    story = []
    story.append(Paragraph("Curated Literature: AI/ML in Earth & Planetary Astrophysics", title_style))
    story.append(Paragraph("Organized in reverse chronological order (2026 - 2023) | Source: arXiv (astro-ph.EP)", meta_style))
    story.append(Spacer(1, 12))
    
    for year in sorted(curated_data.keys(), reverse=True):
        pubs = curated_data[year]
        if not pubs:
            continue
            
        story.append(Paragraph(f"Publication Year: {year}", year_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E1'), spaceAfter=8))
        
        for idx, item in enumerate(pubs, 1):
            title_text = f"<b>{idx}. {item['title']}</b>"
            authors_text = f"<i>Authors:</i> {item['authors']} ({item['published_date']})"
            keywords_text = f"<b>AI/ML Approaches & Uses:</b> {', '.join(item['aiml_keywords'])}"
            ref_text = (
                f"<b>Reference Info:</b> arXiv:{item['arxiv_id']} | "
                f"Journal: {item['journal_ref']} | DOI: {item['doi']}<br/>"
                f"Link: {item['arxiv_url']} | PDF: {item['pdf_url']}"
            )
            
            story.append(Paragraph(title_text, pub_title_style))
            story.append(Paragraph(authors_text, meta_style))
            story.append(Paragraph(keywords_text, kw_style))
            story.append(Paragraph(ref_text, ref_style))
            story.append(Spacer(1, 8))
            
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ==========================================
# STREAMLIT USER INTERFACE
# ==========================================

def main():
    st.set_page_config(
        page_title="Astrophysics AI/ML Literature Curator",
        page_icon="🌌",
        layout="wide"
    )

    st.title("🌌 Earth & Planetary Astrophysics Literature Curator")
    st.caption("Extracts AI/ML publications from arXiv (astro-ph.EP), categorized by year with extracted approaches and citation metadata.")

    # Sidebar Controls
    with st.sidebar:
        st.header("⚙️ Data Sourcing Config")
        
        selected_source = st.selectbox(
            "Select Data Provider",
            ["arXiv (Active)", "Harvard ADS (Coming Soon)"]
        )
        
        st.markdown("---")
        st.subheader("Filter Options")
        target_years = st.multiselect(
            "Publication Years",
            options=[2026, 2025, 2024, 2023],
            default=[2026, 2025, 2024, 2023]
        )
        target_years.sort(reverse=True)
        
        max_pubs_per_year = st.slider("Max Publications per Year", min_value=1, max_value=10, value=10)
        
        st.markdown("---")
        fetch_button = st.button("🔍 Fetch & Curate Literature", type="primary", use_container_width=True)

    # Initialize Session State
    if "curated_results" not in st.session_state:
        st.session_state.curated_results = None

    # Trigger Data Fetch
    if fetch_button:
        if "arXiv" in selected_source:
            with st.spinner("Querying arXiv API for Earth & Planetary Astrophysics AI/ML papers..."):
                results = fetch_arxiv_planetary_aiml(
                    target_years=target_years,
                    max_per_year=max_pubs_per_year
                )
                st.session_state.curated_results = results
                st.success("Curation complete!")
        else:
            st.warning("Selected source is not yet active. Please select arXiv.")

    # Render Results
    curated_data = st.session_state.curated_results

    if curated_data:
        st.markdown("---")
        st.subheader("📥 Export Curated List")
        
        # Download Controls
        col1, col2 = st.columns(2)
        
        # XML Download
        xml_data = generate_xml_output(curated_data)
        col1.download_button(
            label="📄 Download as XML",
            data=xml_data,
            file_name=f"arxiv_astro_ph_EP_AIML_{datetime.date.today()}.xml",
            mime="application/xml",
            use_container_width=True
        )
        
        # PDF Download
        pdf_bytes = generate_pdf_output(curated_data)
        if pdf_bytes:
            col2.download_button(
                label="📕 Download as PDF",
                data=pdf_bytes,
                file_name=f"arxiv_astro_ph_EP_AIML_{datetime.date.today()}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        else:
            col2.info("Install 'reportlab' (`pip install reportlab`) to enable PDF downloads.")

        st.markdown("---")
        st.subheader("📚 Curated Literature List")

        # Display grouped in reverse chronological order
        for year in sorted(curated_data.keys(), reverse=True):
            pubs = curated_data[year]
            
            with st.expander(f"📅 Publication Year: {year} ({len(pubs)} publications)", expanded=True):
                if not pubs:
                    st.info(f"No publications matched the AI/ML criteria for {year}.")
                    continue
                    
                for idx, paper in enumerate(pubs, 1):
                    st.markdown(f"#### {idx}. {paper['title']}")
                    st.markdown(f"**Authors:** {paper['authors']} | **Published:** {paper['published_date']}")
                    
                    # Keywords Display
                    kw_tags = " ".join([f"`{kw}`" for kw in paper['aiml_keywords']])
                    st.markdown(f"**AI/ML Approaches & Uses:** {kw_tags}")
                    
                    # Abstract snippet
                    with st.popover("📖 Read Abstract"):
                        st.write(paper['abstract'])
                        
                    # Reference Information Box
                    st.info(
                        f"**Reference Information:**\n\n"
                        f"- **arXiv Citation:** arXiv:{paper['arxiv_id']} (`astro-ph.EP`)\n"
                        f"- **Journal Reference:** {paper['journal_ref']}\n"
                        f"- **DOI:** {paper['doi']}\n"
                        f"- **Links:** [arXiv Page]({paper['arxiv_url']}) | [PDF Direct Link]({paper['pdf_url']})"
                    )
                    st.markdown("---")


if __name__ == "__main__":
    main()