import zipfile
import xml.etree.ElementTree as ET
import re

pptx_path = '/root/internship-repo/project/Multi-Connectivity and NTN.pptx'
out_path = '/root/internship-repo/project/pptx_slides_extracted.txt'

with zipfile.ZipFile(pptx_path, 'r') as z:
    slide_files = sorted(
        [f for f in z.namelist() if f.startswith('ppt/slides/slide') and f.endswith('.xml')],
        key=lambda x: int(re.search(r'slide(\d+)\.xml', x).group(1))
    )
    with open(out_path, 'w') as out:
        out.write(f"Total slides found: {len(slide_files)}\n\n")
        for i, sf in enumerate(slide_files, 1):
            tree = ET.fromstring(z.read(sf))
            texts = []
            for elem in tree.iter():
                if elem.tag.endswith('}t') and elem.text:
                    t = elem.text.strip()
                    if t:
                        texts.append(t)
            out.write(f"==================== SLIDE {i} ====================\n")
            out.write("\n".join(texts) + "\n\n")

print("Dumped to", out_path)
