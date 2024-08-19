import os         #This for working with the operating system and file system.
import re         # This for regular expressions
import logging    #This for logging messages about the script's execution.
import argparse   #This for parsing command-line arguments
import ujson       # This for working with JSON data
from tqdm import tqdm   # This to Provide a progress bar for the search operation.
from concurrent.futures import ProcessPoolExecutor, as_completed  # This to Enable parallel processing for searching files.


# How to run this script:
# > python search.py /path/to/start_dir --patterns /path/to/patterns.json --output results
# > python search.py /path/to/start_dir --patterns /path/to/patterns.json --output results --file_type .txt,.cfg,.bin --num_workers 4 --verbose
# fix wrong or invalid start_dir and patterns_file


#This function reads the JSON file containing the search patterns and returns them as a dictionary.
def load_patterns(patterns_file):
    with open(patterns_file, 'r') as f:
        patterns = ujson.load(f)
    
    # This to compile patterns into regular expressions
    compiled_patterns = {
        key: [re.compile(pat, re.IGNORECASE) for pat in patterns[key]] if isinstance(patterns[key], list) else re.compile(patterns[key], re.IGNORECASE)
        for key in patterns
    }

    logging.debug(f"Compiled patterns: {compiled_patterns}")
    return compiled_patterns
   
# Function to search the filesystem
def search_filesystem(start_dir, compiled_patterns, file_types=None, binary=False, num_workers=4):
#def search_filesystem(start_dir, patterns, file_types=None, binary=False, num_workers=4):
    """
    Searches a directory recursively for files or binaries matching patterns.

    Args:
        start_dir (str): The starting directory for the search.
        patterns (dict): A dictionary containing the regular expression patterns.
        file_types (list, optional): List of file types to search for (e.g., [".txt",".cfg",".conf"]). Default is None, meaning all files.
        binary (bool, optional): Search only for binary files. Defaults to False.
        num_workers (int, optional): Number of parallel workers. Defaults to 4.

    Returns:
        list: A list of dictionaries containing search results. Each dictionary has keys:
              'filepath', 'matches'.
    """
    results = []
      
    
    logging.debug(f"Compiled patterns: {compiled_patterns}")
    
    
    # This to Check if the file type matches the specified file type
    # This can help reduce the search scope
    def file_matches_type(filename):
        if not file_types:
            return True
        return any(filename.endswith(file_type) for file_type in file_types)
    
    # This to Collect file paths
    filepaths = [
        os.path.join(root, filename)
        for root, _, files in os.walk(start_dir)
        for filename in files if file_matches_type(filename)
    ]
    
    logging.debug(f"Files to be processed: {filepaths}")
    
   
    # Using ProcessPoolExecutor for parallel processing
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_filepath = {
            executor.submit(process_file, filepath, compiled_patterns, binary): filepath
            for filepath in filepaths
        }

        with tqdm(total=len(future_to_filepath), desc="Searching files") as pbar:
            for future in as_completed(future_to_filepath):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as exc:
                    logging.error(f'File {future_to_filepath[future]} generated an exception: {exc}')
                finally:
                    pbar.update(1)

    return results


# Function to process individual files
def process_file(filepath, compiled_patterns, binary):
    """
    Process a single file to find matches for compiled patterns.

    Args:
        filepath (str): The path to the file to be processed.
        compiled_patterns (dict): Dictionary of compiled regular expression patterns.
        binary (bool): Whether to search only in binary files.

    Returns:
        dict: A dictionary containing the filepath and matches or None if no matches are found.
    """
    if binary and not is_binary(filepath):
        return None
        
    logging.debug(f"Processing file: {filepath}")

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore', buffering=1024*1024) as f:  # Open and read the file content
            content = f.read()
            result = {'filepath': filepath, 'matches': {}}
            for key, pattern_list in compiled_patterns.items():
                if isinstance(pattern_list, list):  # Function returns True if the specified pattern is instance of the pattern list, otherwise False
                    matches = [match for pattern in pattern_list for match in pattern.findall(content)] # Search for matches using the compiled patterns
                else:
                    matches = pattern_list.findall(content)
                if matches:
                    result['matches'][key] = matches
        logging.debug(f"Search result for {filepath}: {result}")
    
    # Handle exceptions such as UnicodeDecodeError for binary files    
    except UnicodeDecodeError:
        logging.warning(f"Error decoding file {filepath} (likely binary). Skipping.") # These errors typically happen when the script tries to interpret a file as text (UTF-8 encoding) but the file contains binary data.
        return None
    except Exception as e:
        logging.error(f"Error processing file {filepath}: {e}")
        return None

    if any(result['matches'].values()):
        return result

    return None

# Function to check binary files (used in the process_file function to skip non-binary files when the binary argument is True)
# To search for files that are likely to be binary, such as executable files, binary files, or other non-text files
def is_binary(filepath):
    """
    Check if a file is binary by reading the first 1024 bytes and looking for a NULL character.

    Args:
        filepath (str): The path to the file.

    Returns:
        bool: True if the file is binary, False otherwise.
    """
    with open(filepath, 'rb') as f:
        sample = f.read(1024)
        return b'\x00' in sample  # Check for null byte, a common indicator of binary files

# Function for logging
def setup_logging(verbose):
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Function to generate HTML and JSON reports
def generate_html_output(results, html_file, json_file):
    # Group matches by pattern category
    grouped_results = {}
    for result in results:
        for key, matches in result['matches'].items():
            pattern_category = key.replace('_matches', '').replace('_', ' ').title()
            if pattern_category not in grouped_results:
                grouped_results[pattern_category] = set()
            grouped_results[pattern_category].update(matches)

    html_content = f"""
    <html>
    <head>
        <title>Search Results</title>
        <style>
            table {{
                width: 100%;
                border-collapse: collapse;
            }}
            table, th, td {{
                border: 1px solid black;
            }}
            th, td {{
                padding: 15px;
                text-align: left;
            }}
            th {{
                background-color: #f2f2f2;
            }}
        </style>
    </head>
    <body>
        <h1>Search Results</h1>
        <p>For detailed results, see the <a href="{json_file}">JSON file</a>.</p>
        <table>
            <tr>
                <th>Pattern Category</th>
                <th>Matches</th>
            </tr>
    """

    for category, matches in grouped_results.items():
        matches_html = "<br>".join(str(match) for match in matches)
        html_content += f"""
        <tr>
            <td>{category}</td>
            <td>{matches_html}</td>
        </tr>
        """

    html_content += """
        </table>
    </body>
    </html>
    """

    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

def main():
    print("----------------------------Script is Running---------------------------")

    parser = argparse.ArgumentParser(description="Search files for patterns.")
    parser.add_argument('start_dir', type=str, help="Starting directory for the search.")
    parser.add_argument('--patterns', type=str, required=True, help="Path to the JSON file containing patterns.")
    parser.add_argument('--file_type', type=str, help="File type to search for (e.g., '.txt'). Default is None to search all files.", default=None)
    parser.add_argument('--binary', action='store_true', help="Search only binary files.", default=False)
    parser.add_argument('--num_workers', type=int, help="Number of parallel workers.", default=4)
    parser.add_argument('--verbose', action='store_true', help="Increase output verbosity.", default=False)
    parser.add_argument('--output', type=str, help="Output file prefix.", required=True)

    args = parser.parse_args()
    setup_logging(args.verbose)

    if not os.path.isdir(args.start_dir):
        print(f"Error: {args.start_dir} is not a valid directory.")
        return
    
    if not os.path.isfile(args.patterns):
        print(f"Error: {args.patterns} is not a valid file.")
        return
    
    patterns = load_patterns(args.patterns)

    results = search_filesystem(args.start_dir, patterns, file_types=args.file_type, binary=args.binary, num_workers=args.num_workers)

    output_json = f"{args.output}.json"
    output_html = f"{args.output}.html"

    with open(output_json, 'w', encoding='utf-8') as json_file:
        ujson.dump(results, json_file, indent=4)

    generate_html_output(results, output_html, output_json)

    # Print success message with file locations and sizes
    json_size = os.path.getsize(output_json)
    html_size = os.path.getsize(output_html)

    print("----------------------------------------------------------------")
    print(f"Search completed successfully!")
    print(f"Results saved to: {output_json} (Size: {json_size} bytes)")
    print(f"HTML report saved to: {output_html} (Size: {html_size} bytes)")

if __name__ == "__main__":
    main()
