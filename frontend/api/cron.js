export default async function handler(req, res) {
  try {
    // Ping the Render backend's health endpoint
    const response = await fetch('https://hirekaro.onrender.com/health');
    const data = await response.json();
    
    console.log("Render Ping Successful:", data);
    res.status(200).json({ message: 'Render backend is awake!', data });
  } catch (error) {
    console.error("Render Ping Failed:", error);
    res.status(500).json({ error: 'Failed to ping Render backend' });
  }
}
