"""Paint Products Search Web App

A Streamlit application for searching paint products across multiple catalogs
(Akzo, Crown, PPG) with a simple search bar interface.
"""
import streamlit as st
import pandas as pd
import os
from pathlib import Path
from fuzzywuzzy import fuzz

# Page configuration
st.set_page_config(
    page_title="Paint Products Search",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.title("🎨 Paint Products Search")
st.markdown("Search across Akzo, Crown, and PPG paint catalogs")

# Cache the catalog loading
@st.cache_data
def load_paint_catalogs():
    """Load all paint catalog Excel files."""
    catalogs = {}
    data_dir = os.path.join(os.path.dirname(__file__), 'data', 'paint')
    
    # Define catalog configuration
    catalog_config = {
        'Akzo': {
            'filename': 'akzo.xlsx',
            'code_col': 0,  # Column A
            'desc_col': 4,  # Column E
            'price_col': 40  # Column AO
        },
        'Crown': {
            'filename': 'crown.xlsx',
            'code_col': 0,  # Column A
            'desc_col': 4,  # Column E
            'extra_cols': [6, 7],  # Columns G and H
            'price_col': 17  # Column R
        },
        'PPG': {
            'filename': 'ppg.xlsx',
            'code_col': 0,  # Column A
            'desc_col': 4,  # Column E
            'price_col': 15  # Column P
        }
    }
    
    for catalog_name, config in catalog_config.items():
        filepath = os.path.join(data_dir, config['filename'])
        
        try:
            if os.path.exists(filepath):
                excel_file = pd.ExcelFile(filepath)
                
                # Load the appropriate sheet
                sheet_name = None
                df = None
                
                # Special handling for Crown - use second sheet
                if catalog_name == 'Crown' and len(excel_file.sheet_names) > 1:
                    sheet_name = excel_file.sheet_names[1]
                    df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
                else:
                    # For others, find first sheet with enough columns
                    for sname in excel_file.sheet_names:
                        df_test = pd.read_excel(excel_file, sheet_name=sname, header=None)
                        if df_test.shape[1] > config['desc_col']:
                            sheet_name = sname
                            df = df_test
                            break
                
                if df is not None and sheet_name:
                    # Extract code, description and price columns
                    code_col = config['code_col']
                    desc_col = config['desc_col']
                    price_col = min(config['price_col'], df.shape[1] - 1)
                    extra_cols = config.get('extra_cols', [])
                    
                    # Create a clean dataframe with code, descriptions and prices
                    products = []
                    for idx, row in df.iterrows():
                        code = row.iloc[code_col] if code_col < len(row) else None
                        desc = row.iloc[desc_col] if desc_col < len(row) else None
                        price = row.iloc[price_col] if price_col < len(row) else None
                        
                        # Add extra columns to description (for Crown)
                        if extra_cols:
                            extra_parts = []
                            for col_idx in extra_cols:
                                if col_idx < len(row):
                                    extra = row.iloc[col_idx]
                                    if pd.notna(extra) and str(extra).strip():
                                        extra_parts.append(str(extra).strip())
                            if extra_parts:
                                desc = f"{desc} {' '.join(extra_parts)}" if desc else ' '.join(extra_parts)
                        
                        # Skip empty descriptions
                        if desc and pd.notna(desc) and str(desc).strip():
                            # Format price to 2 decimal places
                            formatted_price = 'N/A'
                            if pd.notna(price) and price != 'N/A':
                                try:
                                    formatted_price = f"£{float(price):.2f}"
                                except (ValueError, TypeError):
                                    formatted_price = str(price)
                            
                            products.append({
                                'Code': code if pd.notna(code) else 'N/A',
                                'Product': str(desc).strip(),
                                'Price': formatted_price,
                                'Catalog': catalog_name
                            })
                    
                    if products:
                        catalogs[catalog_name] = {
                            'data': pd.DataFrame(products),
                            'sheet': sheet_name
                        }
        
        except Exception as e:
            st.warning(f"Could not load {catalog_name} catalog: {e}")
    
    return catalogs

# Load catalogs
catalogs = load_paint_catalogs()

if not catalogs:
    st.error("No paint catalogs found. Please ensure Excel files are in data/paint/ directory.")
else:
    # Create search interface
    col1, col2, col3 = st.columns([2.5, 1.2, 0.8])
    
    with col1:
        search_query = st.text_input(
            "🔍 Search for paint products",
            placeholder="Enter product name, color, or description...",
            help="Search for products"
        )
    
    with col2:

        catalog_filter = st.selectbox(
            "Filter by Catalog:",
            ["All", "Akzo", "Crown", "PPG"],
            key="search_catalog_filter"
        )
    
    with col3:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        search_button = st.button("Search", type="primary", use_container_width=True)
    
    st.divider()
    
    # Perform search if query entered
    if search_query or search_button:
        query_lower = search_query.lower() if search_query else ""
        
        if not query_lower:
            st.info("Enter a search term to find products")
        else:
            # Search across all catalogs using fuzzy matching
            results = []
            
            # Split search query into individual words
            search_terms = query_lower.split()
            
            for catalog_name, catalog_data in catalogs.items():
                df = catalog_data['data'].copy()
                # Use fuzzy matching for both Code and Product columns
                # Calculate match scores for each row - all terms must match
                df['match_score'] = df.apply(
                    lambda row: min(
                        max(
                            fuzz.token_set_ratio(term, str(row['Code']).lower()),
                            fuzz.token_set_ratio(term, row['Product'].lower())
                        )
                        for term in search_terms
                    ) if search_terms else 0,
                    axis=1
                )
                # Keep matches with score >= 50 (50% similarity on ALL terms)
                matching = df[df['match_score'] >= 50].copy()
                matching = matching.drop('match_score', axis=1)
                results.append(matching)
            
            # Combine results
            all_results = pd.concat(results, ignore_index=True) if results else pd.DataFrame()
            
            # Display results
            if len(all_results) > 0:
                # Filter results based on selection
                if catalog_filter == "All":
                    filtered_results = all_results
                else:
                    filtered_results = all_results[all_results['Catalog'] == catalog_filter]
                
                st.success(f"Found {len(filtered_results)} product(s) in {catalog_filter}")
                
                # Display single table with column configuration
                st.dataframe(
                    filtered_results[['Code', 'Product', 'Price', 'Catalog']],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Code": st.column_config.TextColumn(width="small")
                    }
                )
            else:
                st.warning(f"No products found matching '{search_query}'. Try different keywords.")
