"""Generate a real multi-chapter PDF and an image-only scan for local acceptance."""
import os
import pymupdf as fitz

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
DIGITAL = os.path.join(OUT_DIR, "e2e_science.pdf")
SCANNED = os.path.join(OUT_DIR, "e2e_scanned_page.pdf")

CHAPTERS = [
    (
        "Chapter 1: The Fundamental Unit of Life",
        "While examining a thin slice of cork, Robert Hooke saw that the cork resembled the "
        "structure of a honeycomb consisting of many little compartments. Hooke called these "
        "boxes cells. A cell is the basic structural and functional unit of life. The plasma "
        "membrane is the outermost covering of the cell. It separates the contents of the cell "
        "from its external environment and permits the entry and exit of some materials. The "
        "cell membrane is therefore called a selectively permeable membrane. Diffusion is the "
        "spontaneous movement of a substance from a region of high concentration to a region "
        "where its concentration is low. Osmosis is the movement of water across a selectively "
        "permeable membrane.",
    ),
    (
        "Chapter 2: Tissues",
        "A tissue is a group of cells that are similar in structure and work together to achieve "
        "a particular function. Plants have meristematic tissue and permanent tissue. "
        "Meristematic tissue is found at the growing tips of roots and stems and helps the plant "
        "grow. Permanent tissue includes simple tissue such as parenchyma, collenchyma and "
        "sclerenchyma, and complex tissue such as xylem and phloem. Xylem carries water and "
        "minerals upward from the roots. Phloem carries food from the leaves to other parts of "
        "the plant. Animal tissues include epithelial, connective, muscular and nervous tissue. "
        "Epithelial tissue covers the body and lines the internal organs.",
    ),
    (
        "Chapter 3: Diversity in Living Organisms",
        "Living organisms show a wide range of diversity in size, shape, habitat and mode of "
        "nutrition. Classification groups organisms according to shared characteristics. The "
        "five kingdom system places organisms into Monera, Protista, Fungi, Plantae and "
        "Animalia. Monera includes bacteria, which are prokaryotic. Protista includes single "
        "celled eukaryotes such as Amoeba and Paramecium. Fungi include yeast, moulds and "
        "mushrooms. Plantae includes multicellular autotrophs. Animalia includes multicellular "
        "heterotrophs that usually move actively and ingest food.",
    ),
    (
        "Chapter 4: Motion",
        "An object is said to be in motion if its position changes with time with respect to a "
        "reference point. Distance is the total length of the path travelled. Displacement is "
        "the shortest distance from the initial to the final position and has direction. "
        "Speed is distance divided by time. Velocity is displacement divided by time. "
        "Acceleration is the rate of change of velocity. A body moving with uniform velocity "
        "covers equal distances in equal intervals of time in a straight line. Graphs of "
        "distance against time help us compare rest, uniform motion and non-uniform motion.",
    ),
    (
        "Chapter 5: Force and Laws of Motion",
        "Force is a push or a pull that can change the speed, direction or shape of an object. "
        "Newton's first law states that an object remains at rest or in uniform motion in a "
        "straight line unless acted upon by an unbalanced force. Inertia is the tendency of an "
        "object to resist a change in its state of motion. Newton's second law states that the "
        "rate of change of momentum is proportional to the applied force and takes place in "
        "the direction of the force. Newton's third law states that for every action there is "
        "an equal and opposite reaction.",
    ),
    (
        "Chapter 6: Gravitation",
        "Every object in the universe attracts every other object with a force called "
        "gravitational force. The force is directly proportional to the product of the masses "
        "and inversely proportional to the square of the distance between them. The acceleration "
        "due to gravity near the surface of the Earth is approximately nine point eight metres "
        "per second squared. Weight is the force with which the Earth attracts an object. "
        "Mass is the amount of matter in an object and does not change with place, while weight "
        "changes with the value of gravity. Thrust and pressure are related to force acting on "
        "an area.",
    ),
]


def build_digital_pdf():
    doc = fitz.open()
    for title, body in CHAPTERS:
        page = doc.new_page(width=595, height=842)
        page.insert_text((60, 80), title, fontsize=18, fontname="helv")
        words = body.split()
        lines = []
        current = ""
        for word in words:
            candidate = (current + " " + word).strip()
            if len(candidate) > 88:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        y = 130
        for line in lines:
            page.insert_text((60, y), line, fontsize=11, fontname="helv")
            y += 17
    doc.save(DIGITAL)
    doc.close()


def build_scanned_pdf():
    src = fitz.open(DIGITAL)
    first = src[0]
    pix = first.get_pixmap(dpi=120)
    out = fitz.open()
    page = out.new_page(width=first.rect.width, height=first.rect.height)
    page.insert_image(page.rect, pixmap=pix)
    out.save(SCANNED)
    out.close()
    src.close()


if __name__ == "__main__":
    build_digital_pdf()
    build_scanned_pdf()
    print(DIGITAL)
    print(SCANNED)
