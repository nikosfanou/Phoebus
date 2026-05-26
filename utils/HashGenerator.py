import hashlib
import base64

class HashGenerator:
    @staticmethod
    def generate_hash(content: str, algorithm: str, encoding:str="utf-8", return_base64=False) -> str:
        if algorithm not in hashlib.algorithms_available:
            raise Exception(f"This hash algorithm ({algorithm}) is not available.")
        digest = hashlib.new(algorithm, content.encode(encoding=encoding)).digest()
        if return_base64:
            return base64.b64encode(s=digest).decode(encoding=encoding)
        return digest.decode(encoding=encoding)

    @staticmethod
    def generate_hashes(contents: list, algorithm: str, encoding:str="utf-8", return_base64=False) -> list:
        hashes = []
        for content in contents:
            hashes.append(HashGenerator.generate_hash(content=content, algorithm=algorithm, encoding=encoding, return_base64=return_base64))
        return hashes

    @staticmethod
    def generate_sha256(contents: list): # to be used by framework for csp, integrity etc.
        hashes = []
        for content in contents:
            hash = HashGenerator.generate_hash(content=content, algorithm='sha256', encoding='utf-8', return_base64=True)
            hashes.append(f"sha256-{hash}")
        return hashes
