'use client'
import { useState } from 'react'

export default function Home() {
  const [url, setUrl] = useState('')
  const[result, setResult] = useState<string | null>(null)
  const[loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleExtract(){
    setLoading(true)
    setResult(null)
    setError(null)

    try{
      const response = await fetch('http://localhost:8000/extract', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url }),
    })

    const data = await response.json()

    if(!response.ok) {
      throw new Error(data.detail || 'Something went wrong')
    }

    setResult(data.title || 'No title found')

    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main style={{ padding: '40px' }}>
      <h1>Web Scrapper</h1>

      <input
        type="text"
        placeholder='Enter website URL'
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        style={{ width: '400px', padding: '8px' }}
      />

      <br /><br />

      <button onClick={handleExtract} disabled={loading}>
        {loading ? 'Extracting...' : 'Extract'}
      </button>

      <br></br>

      {error && <p style={{ color: 'red' }}>{error}</p>}
      {result && <p><strong>Result:</strong> {result}</p>}
    </main>
  )
}
