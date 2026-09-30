import zipfile
import xml.etree.ElementTree as ET
import re

pptx_path = '/root/internship-repo/project/Multi-Connectivity and NTN.pptx'
with zipfile.ZipFile(pptx_path, 'r') as z:
    slide_files = sorted(
        [f for f in z.namelist() if f.startswith('ppt/slides/slide') and f.endswith('.xml')],
        key=lambda x: int(re.search(r'slide(\d+)\.xml', x).group(1))
    )
    print(f"Total slides found: {len(slide_files)}\n")
    for i, sf in enumerate(slide_files, 1):
        tree = ET.fromstring(z.read(sf))
        # Find all text elements in the slide XML
        texts = []
        for elem in tree.iter():
            if elem.tag.endswith('}t') and elem.text:
                t = elem.text.strip()
                if t:
                    texts.append(t)
        print(f"==================== SLIDE {i} ====================")
        print("\n".join(texts))
        print("\n")
