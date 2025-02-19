import os
import xml.etree.ElementTree as ET

def sanitize_name(name):
    """Sanitize bookmark names to be safe."""
    return "".join(c for c in name if c.isalnum() or c in (" ", "_")).rstrip()

def parse_xbel(file_path):
    """Parse an XBEL file and extract bookmarks with folder structure."""
    bookmarks = []

    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        def traverse(node, parent_name="Favorites"):
            """Recursively traverse the XBEL structure."""
            for child in node:
                if child.tag == "folder":
                    title_elem = child.find("title")
                    folder_name = sanitize_name(title_elem.text) if title_elem is not None else "Unnamed Folder"
                    traverse(child, folder_name)

                elif child.tag == "bookmark":
                    title_elem = child.find("title")
                    title = sanitize_name(title_elem.text) if title_elem is not None else "Untitled"
                    href = child.get("href")
                    if href:
                        bookmarks.append({"title": title, "url": href, "folder": parent_name})

        traverse(root)

    except Exception as e:
        print(f"Error parsing XBEL file: {e}")
        return []

    return bookmarks

def generate_html(bookmarks, output_file):
    """Generate an HTML file in Safari-compatible format."""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write('<!DOCTYPE NETSCAPE-Bookmark-file-1>\n')
        f.write('<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">\n')
        f.write('<TITLE>Bookmarks</TITLE>\n')
        f.write('<H1>Bookmarks</H1>\n')
        f.write('<DL><p>\n')

        folders = {}

        for bookmark in bookmarks:
            folder = bookmark["folder"]
            if folder not in folders:
                f.write(f'    <DT><H3>{folder}</H3>\n')
                f.write('    <DL><p>\n')
                folders[folder] = True

            f.write(f'        <DT><A HREF="{bookmark["url"]}">{bookmark["title"]}</A>\n')

        for folder in folders:
            f.write('    </DL><p>\n')

        f.write('</DL><p>\n')

    print(f"✅ Bookmarks exported to {output_file}")

def main(xbel_file):
    bookmarks = parse_xbel(xbel_file)
    if not bookmarks:
        print("No bookmarks found.")
        return

    output_file = "safari_bookmarks.html"
    generate_html(bookmarks, output_file)
    print("Now import the file manually in Safari.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python export_xbel_to_html.py bookmarks.xbel")
        sys.exit(1)

    main(sys.argv[1])