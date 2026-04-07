from PIL import Image
import imagehash

def get_hash(path):
    return imagehash.phash(Image.open(path))

def is_duplicate(hash1, hash2, threshold=5):
    return abs(hash1 - hash2) < threshold