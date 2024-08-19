import binwalk  #Python module for extracting firmware images
import os       #Provide functionalities for working with the operating system and file system.
import logging  #Python module for logging messages about the script's execution.
import argparse #Python module for parsing command-line arguments


"""
This script automates the process of extracting embedded files from firmware images using Binwalk and the magic library. 
Additionally, it creates a report summarizing the extraction process.
"""
# HOW TO RUN SCRIPT
# > python script.py /path/to/firmware_directory --report report_name

# Configure logging to output messages at the INFO level
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_filesystems(firmware_file, report_file):
    """Extract filesystems from a firmware image using Binwalk and write to report file."""
    try:
        # Run Binwalk with -eM option to extract files
        binwalk.scan(firmware_file, signature=True, quiet=True, extract=True, matryoshka=True, opcodes=True)
        
        # Get the extracted directory
        extracted_dir = os.path.join(os.path.dirname(firmware_file), "_%s.extracted" % os.path.basename(firmware_file))
        
        # Recursively count the number of extracted files
        extracted_files_count = 0
        for root, dirs, files in os.walk(extracted_dir):
            extracted_files_count += len(files)
        
        if extracted_files_count > 0:
            # Write firmware file name with successfully extracted files to report file
            with open(report_file, "a") as report:
                report.write(f"{firmware_file}: Successfully extracted {extracted_files_count} files\n\n")
        else:
            # Write firmware file name with failed extraction to report file
            with open(report_file, "a") as report:
                report.write(f"{firmware_file}: Extraction failed\n\n")
    except Exception as e:
        # Write firmware file name with failed extraction to report file
        with open(report_file, "a") as report:
            report.write(f"{firmware_file}: Extraction failed: {e}\n\n")

def extract_firmware_directory(directory, report_file):
    """Extracts firmware files from a directory, writes results to a report file."""
    firmware_extensions = (".img", ".bin", ".gz", ".dav", ".pak")

    # Check if directory exists and contains firmware files.
    if not os.path.isdir(directory):
        raise RuntimeError(f"Error: Directory not found: {directory}")

    # Clear the report file
    with open(report_file, "w") as report:
        pass

    # Process firmware files in the directory using the extract_filesystems function.
    for root, _, files in os.walk(directory):
        for filename in files:
            if any(filename.endswith(ext) for ext in firmware_extensions): #Check if the file extension matches a supported firmware extension. Call extract_files to extract files from the identified firmware image.
                firmware_file = os.path.join(root, filename)

                # Log processing information
                logging.info(f"Extracting filesystems from {firmware_file}")

                try:
                    extract_filesystems(firmware_file, report_file)
                except RuntimeError as e:
                    logging.error(f"Extraction Failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract filesystems from firmware files in a directory and generate a report.")
    parser.add_argument("firmware_directory", help="Path to the directory containing firmware images")
    parser.add_argument("--report", help="Name of the report file (without extension)", required=True)
    args = parser.parse_args()

    report_file = f"{args.report}.txt"

    try:
        extract_firmware_directory(args.firmware_directory, report_file)
    except RuntimeError as e:
        logging.error(f"Error: {e}")
    else:
        logging.info(f"Report generated: {report_file}")