import hashlib
def get_file_hash(file_path: str) -> str:
    """
    It reads a file (like a PDF) and generates a SHA-256 hash,
      which is a fixed-length unique string representing the file’s content.

    If:
    The file content is exactly the same → hash is the same
    Even 1 byte changes → hash is completely different
    """
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()

# get_file_hash() reads the entire file content and produces a SHA-256 hash.
# SHA-256 guarantees:
# Same content → same hash → same doc_id
# Even 1 byte difference → completely different hash
# So if a user uploads the same PDF file again, the hash will be identical → same doc_id.


# Even one single byte change in the file will produce a completely different hash.
# That means if you change one word in the PDF, the doc_id will be different, because the file content is no longer exactly the same.