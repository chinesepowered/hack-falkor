import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource-variable/inter';
import '@fontsource-variable/nunito';
import './styles/app.css';
import './styles/capy-animations.css';
import './styles/cards.css';
import App from './App';
import DemoCard from './components/DemoCard';

const card = new URLSearchParams(window.location.search).get('card');

createRoot(document.getElementById('root')!).render(
  <StrictMode>{card ? <DemoCard kind={card} /> : <App />}</StrictMode>,
);
