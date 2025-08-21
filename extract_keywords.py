#!/usr/bin/env python3
import json
import csv
from pathlib import Path

def extract_keywords_from_json_files(output_dir, csv_output_path):
    """
    Extract keywords from JSON files in the output directory and save to CSV.
    
    Args:
        output_dir: Path to the directory containing JSON files
        csv_output_path: Path where the CSV file will be saved
    """
    keywords_data = []
    seen_keywords = {}  # Will track (keyword, type, language) tuples
    
    # Get all JSON files in the output directory
    json_files = list(Path(output_dir).glob('*.json'))
    
    print(f"Found {len(json_files)} JSON files to process")
    
    for json_file in json_files:
        # Skip the invalid_files.json if it exists
        if json_file.name == 'invalid_files.json':
            continue
            
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Get the language from metaLanguage field
            language = data.get('metaLanguage', '')
            
            # Process notices array if it exists
            if 'notices' in data and isinstance(data['notices'], list):
                for notice in data['notices']:
                    # Extract keywordsCassation
                    if 'keywordsCassation' in notice and isinstance(notice['keywordsCassation'], list):
                        for keyword in notice['keywordsCassation']:
                            if keyword:
                                key = (keyword, 'Cassation', language)
                                if key not in seen_keywords:
                                    keywords_data.append({
                                        'keyword': keyword,
                                        'type': 'Cassation',
                                        'language': language
                                    })
                                    seen_keywords[key] = True
                    
                    # Extract keywordsUtu
                    if 'keywordsUtu' in notice and isinstance(notice['keywordsUtu'], list):
                        for keyword in notice['keywordsUtu']:
                            if keyword:
                                key = (keyword, 'Utu', language)
                                if key not in seen_keywords:
                                    keywords_data.append({
                                        'keyword': keyword,
                                        'type': 'Utu',
                                        'language': language
                                    })
                                    seen_keywords[key] = True
                                
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error processing {json_file.name}: {e}")
            continue
    
    # Write to CSV
    with open(csv_output_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['keyword', 'type', 'language']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for row in keywords_data:
            writer.writerow(row)
    
    # Calculate statistics
    cassation_keywords = set((k, l) for k, t, l in seen_keywords.keys() if t == 'Cassation')
    utu_keywords = set((k, l) for k, t, l in seen_keywords.keys() if t == 'Utu')
    languages = set(l for _, _, l in seen_keywords.keys())
    
    # Track keywords that appear in multiple contexts
    keyword_occurrences = {}
    for keyword, type_val, lang in seen_keywords.keys():
        if keyword not in keyword_occurrences:
            keyword_occurrences[keyword] = {'types': set(), 'languages': set(), 'count': 0}
        keyword_occurrences[keyword]['types'].add(type_val)
        keyword_occurrences[keyword]['languages'].add(lang)
        keyword_occurrences[keyword]['count'] += 1
    
    # Find keywords with duplicates (appear in multiple languages or types)
    duplicates = {k: v for k, v in keyword_occurrences.items() 
                  if len(v['languages']) > 1 or len(v['types']) > 1}
    
    # Sort by count of occurrences
    sorted_duplicates = sorted(duplicates.items(), key=lambda x: x[1]['count'], reverse=True)
    
    print(f"\nExtraction complete!")
    print(f"Total unique Cassation keywords: {len(cassation_keywords)}")
    print(f"Total unique Utu keywords: {len(utu_keywords)}")
    print(f"Languages found: {', '.join(sorted(languages))}")
    print(f"Total rows in CSV: {len(keywords_data)}")
    print(f"CSV saved to: {csv_output_path}")
    
    print(f"\n{'='*80}")
    print(f"Keywords with duplicates (appearing in multiple languages or types):")
    print(f"{'='*80}")
    print(f"Total keywords with duplicates: {len(duplicates)}\n")
    
    # Show top 20 keywords with most duplicates
    print("Top 20 keywords with most occurrences:")
    print(f"{'Keyword':<60} {'Count':<8} {'Types':<20} {'Languages'}")
    print(f"{'-'*120}")
    
    for keyword, info in sorted_duplicates[:20]:
        types_str = ', '.join(sorted(info['types']))
        langs_str = ', '.join(sorted(info['languages']))
        # Truncate keyword if too long
        display_keyword = keyword[:57] + '...' if len(keyword) > 60 else keyword
        print(f"{display_keyword:<60} {info['count']:<8} {types_str:<20} {langs_str}")
    
    # Show statistics about cross-type and cross-language duplicates
    cross_type = [k for k, v in duplicates.items() if len(v['types']) > 1]
    cross_lang = [k for k, v in duplicates.items() if len(v['languages']) > 1]
    
    print(f"\n{'='*80}")
    print(f"Duplicate Statistics:")
    print(f"{'='*80}")
    print(f"Keywords appearing in both Cassation and Utu: {len(cross_type)}")
    print(f"Keywords appearing in multiple languages: {len(cross_lang)}")
    
    if cross_type:
        print(f"\nExamples of keywords in both types (first 5):")
        for keyword in cross_type[:5]:
            print(f"  - {keyword}")

if __name__ == "__main__":
    # Define paths
    output_directory = "/Users/shaharzep/juportal-decisions-parser/output"
    csv_output_file = "/Users/shaharzep/juportal-decisions-parser/keywords_extracted.csv"
    
    # Run extraction
    extract_keywords_from_json_files(output_directory, csv_output_file)