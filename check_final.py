import os
import tarfile
import sys
import re

def extract_tar_gz(archive_path, extract_to):
    """Extract a .tar.gz archive to a specified directory."""
    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(path=extract_to)
            print(f"Extracted {archive_path} to {extract_to}")
    except Exception as e:
        print(f"Error extracting archive: {e}")
        sys.exit(1)

def check_directive(file_path, directive, expected_value):
    """Check if a directive in the given file is set to the expected value."""
    try:
        with open(file_path, "r") as file:
            for line in file:
                if directive in line and not line.strip().startswith("#"):
                    if expected_value in line:
                        print(f"{directive} is correctly set to {expected_value}.")
                        return True
                    else:
                        print(f"{directive} is not set to {expected_value}: {line.strip()}")
                        return False
        print(f"{directive} directive not found.")
        return False
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)

def check_directory_directives(file_path, directory, directives):
    """Check for specific directives within a given <Directory> block."""
    try:
        with open(file_path, "r") as file:
            content = file.read()

        # Extract the <Directory> block for the specified directory
        pattern = rf"<Directory\s+{re.escape(directory)}/?>(.*?)</Directory>"
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        if not matches:
            print(f"No <Directory {directory}> block found.")
            return False

        # Check each directive in the block
        all_directives_ok = True

        for match in matches:
            directory_block = match

            for directive, expected_value in directives.items():
                directive_pattern = rf"^\s*{directive}\s+{re.escape(expected_value)}"
                if not re.search(directive_pattern, directory_block, re.MULTILINE | re.IGNORECASE):
                    print(f"{directive} is not set to {expected_value} in <Directory {directory}>.")
                    all_directives_ok = False
                else:
                    print(f"{directive} is correctly set to {expected_value} in <Directory {directory}>.")
            print("-----------------------------")
            print(directory_block)
            print("-----------------------------")
        return all_directives_ok
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)

def check_firewall_status(file_path):
    try:
        with open(file_path, "r") as file:
            content = file.read()
        
        # Check if firewall is active
        if "Status: active" not in content:
            print("Firewall is not active.")
            return False
        
        print("Firewall is active.")
        
        # Check if port 80 and 22 are allowed
        required_ports = {"80", "22"}
        allowed_ports = set()
        
        for line in content.splitlines():
            if "ALLOW" in line:
                print(line)
                port = line.split()[0]
                allowed_ports.add(port)
        
        missing_ports = required_ports - allowed_ports
        if missing_ports:
            print(f"The following required ports are not allowed: {', '.join(missing_ports)}")
            return False
        else:
            print("Ports 80 and 22 are allowed.")
            return True

    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

def check_mysql_root_password(file_path):
    try:
        with open(file_path, "r") as file:
            lines = file.readlines()

        # Find the MySQL user-password table
        mysql_section_found = False
        for i, line in enumerate(lines):
            if line.strip() == "checkMySQL":
                mysql_section_found = True
                table_start = i + 1  # Skip the header row
                break

        if not mysql_section_found:
            print("MySQL section not found in the file.")
            return False

        # Check if error while logging in
        for line in lines[table_start:]:
            if "1045" in line:
                print("Root has password!")
                return True
        
        # Check if root has a password
        for line in lines[table_start:]:
            line = line.strip()
            if not line:  # Stop at the end of the table
                break
            parts = line.split(maxsplit=1)
            user = parts[0]
            password = parts[1] if len(parts) > 1 else ""
            if user == "root":
                if password:  # Password exists
                    print("Root has a password.")
                    return True
                else:  # No password for root
                    print("Root does not have a password.")
                    return False

        print("Root user not found in the MySQL section.")
        return False

    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

def check_prepare_statements(file_path):
    prepare_count = 0
    with open(file_path, "r", encoding="utf-8") as file:
        for line in file:
            # Check if the line contains '->prepare('
            if "->prepare(" in line:
                prepare_count += 1
    return prepare_count

import re

def extract_openssl_functions_encrypt(file_path):
    try:
        with open(file_path, "r") as file:
            content = file.read()

        # Regex to match PHP functions
        function_pattern = re.compile(
            r"function\s+(\w+)\s*\((.*?)\)\s*\{(.*?)\}",
            re.DOTALL
        )
        
        # Find all functions
        functions = function_pattern.findall(content)

        # Check each function for openssl_encrypt usage
        openssl_functions = []
        for func_name, params, body in functions:
            if "openssl_encrypt" in body:
                openssl_functions.append(func_name)

        # Print the results
        if openssl_functions:
            print("Functions using openssl_encrypt:")
            for func in openssl_functions:
                print(f"- {func}")
        else:
            print("No functions use openssl_encrypt.")

    except FileNotFoundError:
        print(f"File not found: {file_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

def extract_functions(file_path, function_name):
    try:
        with open(file_path, "r") as file:
            content = file.read()

        # Regex to match PHP functions
        function_pattern = re.compile(
            r"function\s+(\w+)\s*\((.*?)\)\s*\{(.*?)\}",
            re.DOTALL
        )
        
        # Find all functions
        functions = function_pattern.findall(content)

        # Check each function for openssl_encrypt usage
        openssl_functions = []
        for func_name, params, body in functions:
            if function_name in body:
                openssl_functions.append(func_name)

        # Print the results
        if openssl_functions:
            print(f"Functions using {function_name}:")
            for func in openssl_functions:
                print(f"- {func}")
        else:
            print(f"No functions use {function_name}.")

    except FileNotFoundError:
        print(f"File not found: {file_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

def check_function_use(file_path, function_name):
    try:
        with open(file_path, "r") as file:
            content = file.read()

        if function_name in content:
            print(f"{function_name} is used in the file.")
        else:
            print(f"File do not use {function_name}.")

    except FileNotFoundError:
        print(f"File not found: {file_path}")
    except Exception as e:
        print(f"An error occurred: {e}")


def extract_if_blocks(file_path):
    try:
        # Read the PHP file
        with open(file_path, "r") as file:
            content = file.read()

        # Regular expression to match `if` blocks
        if_block_pattern = re.compile(r"if\s*\(.*?\)\s*\{.*?\}", re.DOTALL)

        # Find all `if` blocks
        matches = if_block_pattern.findall(content)

        if matches:
            print("Found the following if blocks:")
            for match in matches:
                print("------")
                print(match)
                print("------")
        else:
            print("No if blocks found in the file.")

    except FileNotFoundError:
        print(f"File not found: {file_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python check_apache_config.py <archive.tar.gz>")
        sys.exit(1)

    archive_path = sys.argv[1]
    if not os.path.isfile(archive_path):
        print(f"File does not exist: {archive_path}")
        sys.exit(1)

    # Define the extraction directory
    archive_name = os.path.splitext(os.path.splitext(os.path.basename(archive_path))[0])[0]
    extract_to = "extracted_apache2"
    final_extract_path = os.path.join(extract_to, archive_name)

    # Extract the tar.gz archive
    extract_tar_gz(archive_path, extract_to)

    # Define paths to files
    security_conf_path = os.path.join(final_extract_path, "apache2", "conf-enabled", "security.conf")
    apache2_conf_path = os.path.join(final_extract_path, "apache2", "apache2.conf")
    exam_report_path = os.path.join(final_extract_path, "exam_report.txt")
    database_path = os.path.join(final_extract_path, "www", "database.php")
    monmur_path = os.path.join(final_extract_path, "www", "monmur.php")
    commun_path = os.path.join(final_extract_path, "www", "commun.php")

    print()
    print("Protection injection SQL ----------------------------------------------------")
    prepare_count = check_prepare_statements(database_path)
    print(f"Number of prepare statements found: {prepare_count}")

    print()
    print("Protection XSS  ----------------------------------------------------")
    check_function_use(monmur_path, "strip_tags")
    check_function_use(database_path, "strip_tags")
    check_function_use(database_path, "htmlspecialchars")
    check_function_use(monmur_path, "htmlspecialchars")

    print()
    print("Protection Upload  ----------------------------------------------------")
    extract_if_blocks(monmur_path)
    extract_if_blocks(commun_path)


    print()
    print("Mot de passe chiffré ----------------------------------------------------")

    extract_functions(database_path, "password_hash")
    extract_functions(database_path, "password_verify")

    print()
    print("Commentaires chiffrés ----------------------------------------------------")

    extract_functions(database_path, "openssl_encrypt")
    extract_functions(database_path, "openssl_decrypt")
    print()
    print("Sécuriser MySQL ----------------------------------------------------")
    if check_mysql_root_password(exam_report_path):
        print("MySQL root password check passed.")
    else:
        print("MySQL root password check failed.")

    print() 
    print("Réduire surface d'attaque ------------------------------------------")
    if check_firewall_status(exam_report_path):
        print("Firewall configuration is correct.")
    else:
        print("Firewall configuration is incorrect.")

    print()
    print("Configurations Apache ---------------------------------------------------")
    # Check the ServerTokens directive
    token_check = check_directive(security_conf_path, "ServerTokens", "Minimal")

    # Check the ServerSignature directive
    signature_check = check_directive(security_conf_path, "ServerSignature", "Off")

    # Check the <Directory /var/www> block in apache2.conf
    directory_directives = {
        "AllowOverride": "None",
        "Options": "-Indexes"
    }
    directory_check = check_directory_directives(apache2_conf_path, "/var/www", directory_directives)

    if token_check and signature_check and directory_check:
        print("All directives are correctly configured.")
    else:
        print("Some directives are not correctly configured.")

if __name__ == "__main__":
    main()