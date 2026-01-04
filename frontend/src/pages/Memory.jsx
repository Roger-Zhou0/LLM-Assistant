// import React, { useEffect, useState } from "react";
// import { useAuth } from "../hooks/useAuth";

// export default function Memory() {
//   const { token } = useAuth();
//   const [memoryList, setMemoryList] = useState([]);
//   const [offset, setOffset] = useState(0);
//   const [limit] = useState(10);
//   const [newEntry, setNewEntry] = useState("");
//   const [loading, setLoading] = useState(false);
//   const [error, setError] = useState("");

//   // 1) Fetch memory on mount and whenever offset changes
//   useEffect(() => {
//     if (!token) return;

//     setLoading(true);
//     fetch(`http://localhost:8000/api/memory?offset=${offset}&limit=${limit}`, {
//       headers: {
//         "Content-Type": "application/json",
//         Authorization: `Bearer ${token}`,
//       },
//     })
//       .then((res) => {
//         if (!res.ok) throw new Error("Failed to load memory");
//         return res.json();
//       })
//       .then((data) => {
//         setMemoryList(data.memory || []);
//       })
//       .catch((err) => setError(err.message))
//       .finally(() => setLoading(false));
//   }, [token, offset, limit]);

//   // 2) “Remember” a new string
//   const handleRemember = async (e) => {
//     e.preventDefault();
//     if (!newEntry.trim()) return;

//     setLoading(true);
//     setError("");
//     try {
//       const res = await fetch("http://localhost:8000/remember", {
//         method: "POST",
//         headers: {
//           "Content-Type": "application/json",
//           Authorization: `Bearer ${token}`,
//         },
//         body: JSON.stringify({ query: newEntry.trim() }),
//       });
//       if (!res.ok) {
//         const err = await res.json();
//         throw new Error(err.detail || "Failed to remember");
//       }
//       setNewEntry("");
//       // Reload from offset = 0 to show the new entry at top
//       setOffset(0);
//     } catch (err) {
//       setError(err.message);
//     } finally {
//       setLoading(false);
//     }
//   };

//   // 3) Delete a single memory entry
//   const deleteEntry = async (index) => {
//     setLoading(true);
//     setError("");
//     try {
//       const res = await fetch(`http://localhost:8000/api/memory/${index}`, {
//         method: "DELETE",
//         headers: {
//           Authorization: `Bearer ${token}`,
//         },
//       });
//       if (!res.ok) {
//         const err = await res.json();
//         throw new Error(err.detail || "Failed to delete");
//       }
//       // Reload current page
//       setOffset(0);
//     } catch (err) {
//       setError(err.message);
//     } finally {
//       setLoading(false);
//     }
//   };

//   // 4) Clear all memory
//   const clearAll = async () => {
//     setLoading(true);
//     setError("");
//     try {
//       const res = await fetch("http://localhost:8000/api/memory", {
//         method: "DELETE",
//         headers: {
//           Authorization: `Bearer ${token}`,
//         },
//       });
//       if (!res.ok) {
//         const err = await res.json();
//         throw new Error(err.detail || "Failed to clear");
//       }
//       // Reload to show empty list
//       setOffset(0);
//     } catch (err) {
//       setError(err.message);
//     } finally {
//       setLoading(false);
//     }
//   };

//   // 5) Pagination controls
//   const prevPage = () => setOffset((prev) => Math.max(prev - limit, 0));
//   const nextPage = () => setOffset((prev) => prev + limit);

//   return (
//     <div className="max-w-3xl mx-auto p-6">
//       <h1 className="text-2xl font-semibold mb-4">Your Memory</h1>

//       {/* Show errors */}
//       {error && <p className="text-red-500 mb-4">{error}</p>}

//       {/* Form to add a new memory entry */}
//       <form onSubmit={handleRemember} className="mb-6 flex gap-2">
//         <input
//           type="text"
//           value={newEntry}
//           onChange={(e) => setNewEntry(e.target.value)}
//           placeholder="Enter something to remember..."
//           className="flex-grow border rounded px-3 py-2"
//         />
//         <button
//           type="submit"
//           disabled={loading || !newEntry.trim()}
//           className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50"
//         >
//           {loading ? "..." : "Remember"}
//         </button>
//       </form>

//       {/* Clear all button */}
//       <button
//         onClick={clearAll}
//         disabled={loading}
//         className="mb-6 text-sm text-red-600 hover:underline disabled:opacity-50"
//       >
//         Clear All Memory
//       </button>

//       {/* Memory list */}
//       {loading ? (
//         <p>Loading…</p>
//       ) : memoryList.length === 0 ? (
//         <p className="text-gray-600">No memory entries to display.</p>
//       ) : (
//         <ul className="space-y-4">
//           {memoryList.map((entry, idx) => (
//             <li key={offset + idx} className="flex justify-between items-start">
//               <p className="whitespace-pre-wrap">{entry}</p>
//               <button
//                 onClick={() => deleteEntry(offset + idx)}
//                 disabled={loading}
//                 className="text-red-500 text-sm hover:underline disabled:opacity-50 ml-4"
//               >
//                 Delete
//               </button>
//             </li>
//           ))}
//         </ul>
//       )}

//       {/* Pagination */}
//       <div className="mt-6 flex justify-between">
//         <button
//           onClick={prevPage}
//           disabled={loading || offset === 0}
//           className="px-4 py-2 bg-gray-200 rounded disabled:opacity-50"
//         >
//           Previous
//         </button>
//         <button
//           onClick={nextPage}
//           disabled={loading || memoryList.length < limit}
//           className="px-4 py-2 bg-gray-200 rounded disabled:opacity-50"
//         >
//           Next
//         </button>
//       </div>
//     </div>
//   );
// }
