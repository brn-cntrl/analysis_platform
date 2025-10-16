import React from 'react';
import AnalysisViewer from './components/AnalysisViewer';
import ResultsViewer from './components/ResultsViewer';

function App() {
  const path = window.location.pathname;
  
  if (path === '/results') {
    return <ResultsViewer />;
  }
  
  return <AnalysisViewer />;
}

export default App;