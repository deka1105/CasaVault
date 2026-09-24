async function checkHealth() {
  const res = await fetch("/api/health");
  const data = await res.json();
  console.log("CasaVault backend:", data);
}

checkHealth();
