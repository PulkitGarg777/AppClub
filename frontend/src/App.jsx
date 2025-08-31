import React, {useEffect, useState} from "react";

export default function App(){
  const [rows, setRows] = useState([]);
  async function load(){
    const res = await fetch("/api/applications");
    const data = await res.json();
    setRows(data);
  }
  useEffect(()=>{load()},[]);
  return (
    <div style={{fontFamily:"Arial,Helvetica,sans-serif", padding:20}}>
      <h1>Internship Application Organizer</h1>
      <div style={{marginBottom:10}}>
        <button onClick={load}>Refresh</button>{" "}
        <a href="/api/export" target="_blank" rel="noreferrer"><button>Export CSV</button></a>
      </div>
      <table style={{borderCollapse:"collapse", width:"100%"}}>
        <thead><tr><th style={{border:"1px solid #ddd",padding:8}}>Company</th><th style={{border:"1px solid #ddd",padding:8}}>Title</th><th style={{border:"1px solid #ddd",padding:8}}>Job ID</th><th style={{border:"1px solid #ddd",padding:8}}>Date</th><th style={{border:"1px solid #ddd",padding:8}}>Status</th></tr></thead>
        <tbody>
          {rows.length===0 && <tr><td colSpan={5}>No entries</td></tr>}
          {rows.map(r=>(<tr key={r.id}><td style={{border:"1px solid #ddd",padding:8}}>{r.company_name}</td><td style={{border:"1px solid #ddd",padding:8}}>{r.title}</td><td style={{border:"1px solid #ddd",padding:8}}>{r.job_id}</td><td style={{border:"1px solid #ddd",padding:8}}>{r.application_date?new Date(r.application_date).toLocaleString():""}</td><td style={{border:"1px solid #ddd",padding:8}}>{r.status}</td></tr>))}
        </tbody>
      </table>
    </div>
  );
}