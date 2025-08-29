import { useState } from "react";

function App() {
  const [role, setRole] = useState("");
  const [skills, setSkills] = useState("");
  const [location, setLocation] = useState("");
  const [prospects, setProspects] = useState([]);

  const fetchProspects = async () => {
    const params = new URLSearchParams({ role, skills, location });
    const res = await fetch(http://127.0.0.1:8000/prospects?${params});
    const data = await res.json();
    setProspects(data);
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">HR Prospect Finder</h1>
      
      <div className="flex gap-2 mb-4">
        <input 
          className="border p-2 rounded w-1/3" 
          placeholder="Role" 
          value={role} 
          onChange={(e) => setRole(e.target.value)} 
        />
        <input 
          className="border p-2 rounded w-1/3" 
          placeholder="Skills (comma-separated)" 
          value={skills} 
          onChange={(e) => setSkills(e.target.value)} 
        />
        <input 
          className="border p-2 rounded w-1/3" 
          placeholder="Location" 
          value={location} 
          onChange={(e) => setLocation(e.target.value)} 
        />
        <button 
          onClick={fetchProspects} 
          className="bg-blue-600 text-white px-4 py-2 rounded"
        >
          Search
        </button>
      </div>

      <table className="w-full border">
        <thead>
          <tr className="bg-gray-200">
            <th className="border p-2">Name</th>
            <th className="border p-2">Role</th>
            <th className="border p-2">Email</th>
            <th className="border p-2">Fit</th>
            <th className="border p-2">Profile</th>
          </tr>
        </thead>
        <tbody>
          {prospects.map((p, idx) => (
            <tr key={idx} className="text-sm">
              <td className="border p-2">{p.full_name}</td>
              <td className="border p-2">{p.role}</td>
              <td className="border p-2">{p.email || "N/A"}</td>
              <td className="border p-2">{p.fit}</td>
              <td className="border p-2">
                <a href={p.profile_url} target="_blank" className="text-blue-600 underline">View</a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;