import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import ChatInterface from "./ChatInterface";

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Navigate to="/chat" />} />
        <Route path="/chat" element={<ChatInterface />} />
      </Routes>
    </Router>
  );
}

export default App;
