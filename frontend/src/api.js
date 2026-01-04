const API_BASE = import.meta.env.VITE_API_BASE_URL;

export async function askQuestion(query) {
  const res = await fetch(`${API_BASE}/ask`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query }),
  });

  if (!res.ok) {
    throw new Error('Failed to fetch answer');
  }

  return await res.json();
}

export async function uploadFile(file) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error("File upload failed");
  }

  return await res.json();
}

export async function fetchMemoryPreview() {
  const res = await fetch(`${API_BASE}/api/memory`);
  if (!res.ok) {
    throw new Error('Failed to fetch memory preview');
  }
  return await res.json();
}
