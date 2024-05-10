import hashlib
# from plugin.source import SourceFile

def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def hash_equal(path1, path2):
    # if isinstance(path1, SourceFile):
    #     return path1.md5 == md5(path2)
    return md5(path1) == md5(path2)
