import axios from 'axios'

const API = axios.create({ baseURL: '/api' })

export async function health() {
  const res = await API.get('/health')
  return res.data
}

export async function approve(verdict: string, modifiedAction?: unknown) {
  const res = await API.post('/approve', { verdict, modified_action: modifiedAction })
  return res.data
}
