from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

c = QdrantClient("http://localhost:6333")
coll = "sop"

# 1. Delete the TDD docx
r = c.delete(coll, points_selector=Filter(must=[FieldCondition(key="filename", match=MatchValue(value="DataIngestion-TDD-v0_2.docx"))]))
print("Deleted TDD docx:", r)

# 2. Delete the test sample PDF
r = c.delete(coll, points_selector=Filter(must=[FieldCondition(key="filename", match=MatchValue(value="test_sample.pdf"))]))
print("Deleted test sample PDF:", r)

# 3. Dedup the SOP PDF — keep first occurrence of each chunk_index, delete the rest
seen = {}
to_delete = []
offset = None
while True:
    pts, offset = c.scroll(coll, limit=250, offset=offset, with_payload=["filename", "chunk_index"], with_vectors=False)
    for p in pts:
        key = ((p.payload or {}).get("filename"), (p.payload or {}).get("chunk_index"))
        if key in seen:
            to_delete.append(str(p.id))
        else:
            seen[key] = str(p.id)
    if offset is None:
        break

print(f"Duplicate SOP points to delete: {len(to_delete)}")
if to_delete:
    c.delete(coll, points_selector=to_delete)
    print("Dedup done.")

# 4. Verify
info = c.get_collection(coll)
print(f"SOP collection now has {info.points_count} points")
