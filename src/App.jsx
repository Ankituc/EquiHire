import { useEffect, useRef, useState } from 'react';
import {
  Activity, AlertCircle, ArrowRight, Check, CircleHelp, FileText, FileUp, Home, Info, LockKeyhole,
  Pencil, RotateCcw, Scale, ShieldCheck, Upload, Wifi, WifiOff, X,
} from 'lucide-react';

async function fileToBase64(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = '';
  const chunkSize = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
  }
  return btoa(binary);
}

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const ROLE_SUGGESTIONS = [
  'Data Analyst', 'Data Scientist', 'Machine Learning Engineer', 'AI Engineer', 'Data Engineer',
  'Frontend Developer', 'Backend Developer', 'Full Stack Developer', 'Python Developer', 'C++ Developer',
  'Java Developer', 'Cloud Engineer', 'DevOps Engineer', 'Cybersecurity Analyst', 'QA Engineer',
  'Mobile Developer', 'UX Designer', 'Product Analyst', 'Business Analyst', 'Research Assistant',
];

const navItems = [
  { label: 'Overview', href: '#top', icon: Home },
  { label: 'Resume review', href: '#resume-review', icon: FileText, active: true },
  { label: 'Model performance', href: '#model-performance', icon: Activity },
  { label: 'Fairness & guidance', href: '#fairness-guidance', icon: Scale },
  { label: 'Career directions', href: '#career-directions', icon: ArrowRight },
];

function Modal({ titleId, onClose, children, className = '' }) {
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className={`modal ${className}`} role="dialog" aria-modal="true" aria-labelledby={titleId}>
        {children}
      </section>
    </div>
  );
}

function BenchmarkSection({ benchmark }) {
  const modelLabels = [
    ['mean_baseline', 'Mean baseline'],
    ['decision_tree', 'Decision Tree'],
    ['knn', 'KNN'],
    ['ridge', 'Ridge'],
  ];
  const maxMae = Math.max(...modelLabels.map(([key]) => benchmark?.models?.[key]?.mae || 0), 0.01);
  const domains = Object.keys(benchmark?.models?.knn?.mae_by_domain || {});

  return (
    <section className="benchmark-section" id="model-performance" aria-label="Model benchmark results">
      <div className="analytics-heading"><div><p className="eyebrow">OFFLINE EVALUATION</p><h2>Model performance</h2><p>Grouped cross-validation against expert relevance ratings; intervals resample whole resume IDs.</p></div><span className="analysis-method">{benchmark ? `${benchmark.rows} resumes · ${benchmark.evaluation}` : 'Decision Tree · KNN · Ridge regression'}</span></div>
      {benchmark ? <div className="benchmark-grid">
        <article className="panel benchmark-overview"><div className="chart-title"><div><h3>Regression error</h3><p>Lower MAE and RMSE are better; intervals show resampling uncertainty</p></div></div>{modelLabels.map(([key, label]) => { const metrics = benchmark.models[key]; if (!metrics) return null; return <div className="benchmark-model-row" key={key}><div className="benchmark-model-label"><span>{label}</span><strong>MAE {metrics.mae.toFixed(3)}</strong></div><div className="benchmark-track"><span className={key === 'knn' ? 'best-model' : ''} style={{ width: `${Math.max(4, metrics.mae / maxMae * 100)}%` }} /></div><small>{key !== 'mean_baseline' && <>RMSE {metrics.rmse.toFixed(3)} <i>·</i> R² {metrics.r2.toFixed(2)} <i>·</i></>}{metrics.mae_ci_95 && <> 95% MAE CI {metrics.mae_ci_95[0]}–{metrics.mae_ci_95[1]}</>}</small></div>; })}</article>
        <article className="panel benchmark-domain"><div className="chart-title"><div><h3>Per-domain MAE</h3><p>Decision Tree, KNN, and Ridge errors by resume category</p></div></div><div className="domain-table"><div className="domain-table-head"><span>Domain</span><span>Tree</span><span>KNN</span><span>Ridge</span></div>{domains.map((domain) => <div className="domain-table-row" key={domain}><span>{domain}</span><strong>{benchmark.models.decision_tree?.mae_by_domain?.[domain]?.mae?.toFixed(3) ?? '—'}</strong><strong>{benchmark.models.knn?.mae_by_domain?.[domain]?.mae?.toFixed(3) ?? '—'}</strong><strong>{benchmark.models.ridge?.mae_by_domain?.[domain]?.mae?.toFixed(3) ?? '—'}</strong></div>)}</div><p className="annotator-note">Human annotator disagreement: MAE {benchmark.annotator_agreement.mae.toFixed(3)}. Read model errors alongside label variability.</p></article>
        <p className="benchmark-caveat"><Info size={14} />The dataset contains six broad categories and professionally crafted/de-identified examples. These results measure agreement with expert ratings, not hiring outcomes, employee performance, or actual skill proficiency.</p>
      </div> : <article className="panel benchmark-loading"><span className="spinner-small" />Run <code>python -m ml.train_evaluate</code> with the local CareerCorpus workbook to generate this benchmark.</article>}
    </section>
  );
}

function ModelRelevancePanel({ modelRelevance }) {
  return (
    <section className="panel model-relevance-panel">
      <div className="chart-title"><div><p className="eyebrow">CAREERCORPUS BENCHMARK</p><h3>Expert relevance estimate</h3><p>Regression estimates for roles represented in the research dataset.</p></div></div>
      {modelRelevance ? <>
        <div className="model-cards"><div><span className="model-tag">DECISION TREE · SCORE 0–1</span><strong>{Math.round(modelRelevance.estimates.decision_tree * 100)}%</strong><p>Broad relevance estimate for {modelRelevance.domain}.</p></div><div><span className="model-tag">KNN · SCORE 0–1</span><strong>{Math.round(modelRelevance.estimates.knn * 100)}%</strong><p>Broad relevance estimate for {modelRelevance.domain}.</p></div><div><span className="model-tag">RIDGE · SCORE 0–1</span><strong>{Math.round(modelRelevance.estimates.ridge * 100)}%</strong><p>Regularized linear estimate for {modelRelevance.domain}.</p></div></div>
        <p className="model-caveat"><Info size={14} />Models were fit on {modelRelevance.training_rows} de-identified research examples. This score is not hiring probability or skill proficiency.</p>
      </> : <p className="model-unavailable">This regression model covers Teacher, Finance, Apparel, Accountant, Banking, and Research Assistant. For other roles, use the requirement-level evidence matching above.</p>}
    </section>
  );
}

function ModelMetricsTicker({ benchmark }) {
  if (!benchmark?.models) return null;
  const modelCards = [
    { key: 'decision_tree', label: 'Decision Tree', accent: 'tree' },
    { key: 'knn', label: 'K-Nearest Neighbors', accent: 'knn' },
    { key: 'ridge', label: 'Ridge Regression', accent: 'ridge' },
    { key: 'mean_baseline', label: 'Mean Baseline', accent: 'baseline' },
  ];
  const renderCard = ({ key, label, accent }) => {
    const metrics = benchmark.models[key];
    if (!metrics) return null;
    return <article className={`ticker-metric-card ticker-${accent}`} key={key}>
      <span className="ticker-card-label">{label}</span>
      <strong>MAE {metrics.mae.toFixed(3)}</strong>
      <span className="ticker-card-detail">RMSE {metrics.rmse.toFixed(3)} <i>·</i> R² {metrics.r2.toFixed(2)}</span>
    </article>;
  };
  const renderContextCards = () => <>
    <article className="ticker-metric-card ticker-context" key="sample-size"><span className="ticker-card-label">Evaluation set</span><strong>{benchmark.rows}</strong><span className="ticker-card-detail">resume examples</span></article>
    <article className="ticker-metric-card ticker-context" key="validation"><span className="ticker-card-label">Validation</span><strong>5-fold</strong><span className="ticker-card-detail">GroupKFold evaluation</span></article>
  </>;
  return <section className="model-ticker" aria-label="Model evaluation metrics">
    <a href="#model-performance" className="ticker-heading"><span className="ticker-heading-mark"><Activity size={15} /></span><span><strong>MODEL EVALUATION</strong><small>CareerCorpus benchmark</small></span></a>
    <div className="ticker-window" tabIndex={0} aria-label="Scroll through model evaluation metrics">
      <div className="ticker-track">
        {[0, 1].map((copy) => <div className="ticker-group" key={copy} aria-hidden={copy === 1 ? 'true' : undefined}>
          {modelCards.map(renderCard)}{renderContextCards()}
        </div>)}
      </div>
    </div>
  </section>;
}

function CareerDirections({ directions, excludedSkills = [] }) {
  return (
    <section className="career-section" id="career-directions" aria-label="Suggested career directions">
      <div className="analytics-heading">
        <div><p className="eyebrow">CAREER EXPLORATION</p><h2>Where your skills could take you</h2><p>Role ideas use resume skill overlap; detected experience is shown as context, not used to infer seniority.</p></div>
        <span className="analysis-method">Resume skill overlap · guidance only</span>
      </div>
      {directions?.length ? <div className="career-grid">
        {directions.map((item, index) => { const matched = item.matched_skills.filter((skill) => !excludedSkills.includes(skill)); const removed = item.matched_skills.filter((skill) => excludedSkills.includes(skill)); const nextSkills = [...new Set([...item.next_skills, ...removed])]; const adjustedMatch = Math.round(matched.length / Math.max(1, item.required_count) * 100); return <article className="panel career-card" key={item.role}>
          <div className="career-card-top"><span className="career-rank">0{index + 1}</span><span className="career-match">{adjustedMatch}% skill overlap</span></div>
          <h3>{item.role}</h3><p className="career-reason">{matched.length} confirmed resume skill signal(s) match this role profile. Experience detected: {item.experience_context || 'Not detected'}.</p>
          <div className="career-skill-group"><span className="career-label">Confirmed from resume</span><div className="career-chips">{matched.length ? matched.map((skill) => <span className="career-chip present" key={skill}>{skill}</span>) : <span className="career-muted">No confirmed skill overlap yet</span>}</div></div>
          {nextSkills.length > 0 && <div className="career-skill-group"><span className="career-label">Potential next skills</span><div className="career-chips">{nextSkills.map((skill) => <span className="career-chip next" key={skill}>{skill}</span>)}</div></div>}
        </article>; })}
      </div> : <article className="panel career-empty"><Info size={17} /><div><strong>Career suggestions will appear after resume review</strong><p>Upload a resume with detectable technical skills to explore related role directions.</p></div></article>}
      <p className="career-disclaimer"><Info size={14} />Suggestions use a transparent overlap with curated role skill profiles. They are starting points for exploration, not assessments of skill level, employability, or hiring outcomes.</p>
    </section>
  );
}

function App() {
  const fileRef = useRef(null);
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [role, setRole] = useState('');
  const [requirements, setRequirements] = useState('');
  const [review, setReview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  const [editing, setEditing] = useState(false);
  const [editDraft, setEditDraft] = useState(null);
  const [showHowItWorks, setShowHowItWorks] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [showNoteEditor, setShowNoteEditor] = useState(false);
  const [noteDraft, setNoteDraft] = useState('');
  const [reviewNote, setReviewNote] = useState('');
  const [benchmark, setBenchmark] = useState(null);
  const [serviceStatus, setServiceStatus] = useState('checking');
  const [draggingFile, setDraggingFile] = useState(false);
  const [excludedCareerSkills, setExcludedCareerSkills] = useState([]);
  const [demoMode, setDemoMode] = useState(false);

  useEffect(() => {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
      setPreviewUrl('');
      return undefined;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  useEffect(() => {
    let active = true;
    async function checkApi() {
      try {
        const response = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(4000) });
        const result = response.ok ? await response.json() : null;
        if (active) setServiceStatus(result?.status === 'ok' ? 'online' : 'offline');
      } catch {
        if (active) setServiceStatus('offline');
      }
    }
    checkApi();
    const intervalId = window.setInterval(checkApi, 15_000);
    return () => { active = false; window.clearInterval(intervalId); };
  }, []);

  useEffect(() => {
    if (!showHowItWorks && !showPreview && !showNoteEditor && !editing) return undefined;
    function closeOnEscape(event) {
      if (event.key !== 'Escape') return;
      setShowHowItWorks(false);
      setShowPreview(false);
      setShowNoteEditor(false);
      setEditing(false);
    }
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [showHowItWorks, showPreview, showNoteEditor, editing]);

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}model_metrics.json`)
      .then((response) => response.ok ? response.json() : null)
      .then((result) => { if (result?.models) setBenchmark(result); })
      .catch(() => setBenchmark(null));
  }, []);

  function chooseFile(nextFile) {
    if (!nextFile) return;
    const extension = nextFile.name.split('.').pop()?.toLowerCase();
    if (!['pdf', 'docx'].includes(extension)) {
      setNotice({ type: 'error', message: 'Choose a PDF or DOCX resume.' });
      if (fileRef.current) fileRef.current.value = '';
      return;
    }
    if (nextFile.size > 10 * 1024 * 1024) {
      setNotice({ type: 'error', message: 'This file is over the 10 MB limit. Choose a smaller resume.' });
      if (fileRef.current) fileRef.current.value = '';
      return;
    }
    setFile(nextFile);
    if (fileRef.current) fileRef.current.value = '';
    setReview(null);
    setReviewNote('');
    setExcludedCareerSkills([]);
    setDemoMode(false);
    setNotice({ type: 'info', message: 'Resume ready. Add a target role, then choose Review resume.' });
  }

  function removeFile() {
    setFile(null);
    setReview(null);
    setReviewNote('');
    setExcludedCareerSkills([]);
    setDemoMode(false);
    if (fileRef.current) fileRef.current.value = '';
    setNotice({ type: 'info', message: 'Resume removed from this session.' });
  }

  async function runReview(event) {
    event.preventDefault();
    if (!file) {
      setNotice({ type: 'error', message: 'Upload a resume before starting the review.' });
      fileRef.current?.click();
      return;
    }
    if (!role.trim()) {
      setNotice({ type: 'error', message: 'Enter the target role you want to review against.' });
      document.getElementById('target-role')?.focus();
      return;
    }
    setBusy(true);
    setNotice(null);
    setReviewNote('');
    try {
      const contentBase64 = await fileToBase64(file);
      const controller = new AbortController();
      const timeoutId = window.setTimeout(() => controller.abort(), 60_000);
      let response;
      try {
        response = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: file.name,
          content_base64: contentBase64,
          target_role: role.trim(),
          job_requirements: requirements.trim(),
        }),
        signal: controller.signal,
        });
      } finally {
        window.clearTimeout(timeoutId);
      }
      let result;
      try { result = await response.json(); } catch { throw new Error('The analysis service returned an unreadable response. Check that the FastAPI server is running.'); }
      if (!response.ok) {
        const detail = Array.isArray(result.detail)
          ? result.detail.map((item) => item.msg).join(' ')
          : result.detail;
        throw new Error(detail || 'The resume could not be analyzed. Check the file and try again.');
      }
      setReview(result);
      setServiceStatus('online');
      setNotice({ type: 'success', message: 'Review complete. Highlighted skills match the selected role criteria.' });
    } catch (error) {
      setReview(null);
      const message = error.name === 'AbortError'
        ? 'Analysis timed out. Try a smaller or text-based resume.'
        : error instanceof TypeError
          ? 'Could not reach the analysis service. Start the FastAPI server, then try again.'
          : error.message;
      setNotice({ type: 'error', message });
    } finally {
      setBusy(false);
    }
  }

  async function loadDemoReview() {
    setBusy(true);
    setNotice(null);
    setFile(null);
    setReviewNote('');
    setExcludedCareerSkills([]);
    if (fileRef.current) fileRef.current.value = '';
    try {
      const response = await fetch(`${API_BASE}/demo`);
      if (!response.ok) throw new Error('Could not load the sample review. Check that the FastAPI server is running.');
      setReview(await response.json());
      setRole('Data Analyst');
      setRequirements('SQL, Python, Power BI, Tableau');
      setDemoMode(true);
      setServiceStatus('online');
      setNotice({ type: 'success', message: 'Synthetic sample loaded. It contains no real candidate information.' });
    } catch (error) {
      setNotice({ type: 'error', message: error.message });
    } finally {
      setBusy(false);
    }
  }

  function clearReview() {
    setReview(null);
    setFile(null);
    setReviewNote('');
    setExcludedCareerSkills([]);
    setDemoMode(false);
    if (fileRef.current) fileRef.current.value = '';
    setNotice({ type: 'info', message: 'Review cleared. The file, results, and note were removed from this session.' });
  }

  function openEditor() {
    setEditDraft({ name: review.name, role: review.role, experience: review.experience, education: review.education, location: review.location });
    setEditing(true);
  }

  function saveDetails(event) {
    event.preventDefault();
    if (!editDraft.name.trim()) return;
    setReview((current) => ({ ...current, ...editDraft, name: editDraft.name.trim() }));
    setEditing(false);
  }

  function saveNote(event) {
    event.preventDefault();
    setReviewNote(noteDraft.trim());
    setShowNoteEditor(false);
  }

  const initials = review?.name.split(/\s+/).map((part) => part[0]).slice(0, 2).join('').toUpperCase() || '—';
  const criteria = review?.criteria || [];
  const matchedCount = criteria.filter((item) => item.found).length;
  const relatedCount = criteria.filter((item) => !item.found && item.similarity >= 12).length;
  const missingCount = Math.max(0, criteria.length - matchedCount - relatedCount);
  const averageSimilarity = criteria.length ? Math.round(criteria.reduce((sum, item) => sum + (item.similarity || 0), 0) / criteria.length) : 0;

  return (
    <div id="top" className="app-shell">
      <a className="skip-link" href="#main-content">Skip to resume review</a>
      <header className="topbar">
        <a className="brand" href="#top" aria-label="EquiHire home"><span className="brand-mark"><i /><i /><i /></span><span>EquiHire</span></a>
        <nav className="main-nav" aria-label="Main navigation">
          {navItems.map(({ label, href, icon: Icon, active }) => <a className={active ? 'nav-link active' : 'nav-link'} href={href} key={label}><Icon size={16} strokeWidth={1.8} /><span>{label}</span></a>)}
        </nav>
        <div className="top-actions">
          <span className={`service-indicator service-${serviceStatus}`} title={serviceStatus === 'online' ? 'Analysis API is reachable' : serviceStatus === 'offline' ? 'Start the FastAPI server to review resumes' : 'Checking the analysis API'} aria-live="polite">{serviceStatus === 'online' ? <Wifi size={14} /> : <WifiOff size={14} />}<span>{serviceStatus === 'online' ? 'API ready' : serviceStatus === 'offline' ? 'API offline' : 'Checking API'}</span></span>
          <button className="quiet-button help-button header-help" onClick={() => setShowHowItWorks(true)}><CircleHelp size={16} />How it works</button>
          <button className="nav-upload" onClick={() => fileRef.current?.click()}><Upload size={15} />Upload resume</button>
        </div>
      </header>

      <section className="hero-splash" aria-label="Upload a resume to begin">
        <div className="hero-shape hero-shape-left" aria-hidden="true" />
        <div className="hero-shape hero-shape-right" aria-hidden="true" />
        <div className="sample-resume sample-resume-left" aria-hidden="true">
          <div className="sample-resume-head"><span className="sample-avatar avatar-indigo">AM</span><span className="sample-resume-label">SAMPLE RESUME</span><FileText size={15} /></div>
          <div className="sample-resume-name">A. Morgan</div><div className="sample-resume-role">Product Designer</div>
          <div className="sample-rule" /><div className="sample-line wide" /><div className="sample-line medium" /><div className="sample-line short" />
          <div className="sample-skill-row"><span>Figma</span><span>Research</span><span>UX</span></div>
        </div>
        <div className="sample-resume sample-resume-right" aria-hidden="true">
          <div className="sample-resume-head"><span className="sample-avatar avatar-teal">RK</span><span className="sample-resume-label">SAMPLE RESUME</span><FileText size={15} /></div>
          <div className="sample-resume-name">R. Kapoor</div><div className="sample-resume-role">Data Analyst</div>
          <div className="sample-rule" /><div className="sample-line wide" /><div className="sample-line medium" /><div className="sample-line short" />
          <div className="sample-skill-row"><span>Python</span><span>SQL</span><span>BI</span></div>
        </div>
        <div className="hero-float-note hero-float-note-left" aria-hidden="true"><span className="hero-note-dot" />Skill evidence, made clearer</div>
        <div className="hero-float-note hero-float-note-right" aria-hidden="true"><span className="hero-note-dot" />Role criteria at a glance</div>
        <div className="hero-center">
          <p className="hero-kicker"><span />EQUIHIRE · RESUME REVIEW</p>
          <h1>A clearer way to review<br /><em>employment fit.</em></h1>
          <p className="hero-copy">Click to upload a resume and compare its skills with role requirements.</p>
          <button className="primary-button hero-upload-button" onClick={() => fileRef.current?.click()}><Upload size={18} />Click to upload resume</button>
          <p className="hero-file-note">PDF or DOCX · Up to 10 MB · Processed in your session</p>
          <button className="hero-demo-link" onClick={loadDemoReview} disabled={busy}>or explore a synthetic sample</button>
        </div>
      </section>
      <ModelMetricsTicker benchmark={benchmark} />

      <main className="page-wrap" id="main-content">
        <section className="intake-panel" id="resume-review" aria-label="Start a resume review">
          <form className="intake-form" onSubmit={runReview}>
            <div className="field-group upload-group">
              <label className="field-label" htmlFor="resume-upload">Resume</label>
              <input ref={fileRef} id="resume-upload" className="visually-hidden" type="file" disabled={busy} accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => chooseFile(event.target.files?.[0])} />
              <div className={`upload-control ${file ? 'has-file' : ''} ${draggingFile ? 'is-dragging' : ''}`} onDragOver={(event) => { event.preventDefault(); if (!busy) setDraggingFile(true); }} onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setDraggingFile(false); }} onDrop={(event) => { event.preventDefault(); setDraggingFile(false); if (!busy) chooseFile(event.dataTransfer.files?.[0]); }}><button className="upload-trigger" type="button" disabled={busy} onClick={() => fileRef.current?.click()}>{file ? <FileText size={19} /> : <Upload size={19} />}<span className="upload-copy"><strong>{file ? file.name : draggingFile ? 'Drop your resume here' : 'Upload resume'}</strong><small>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB · ready to review` : 'Choose or drop a PDF or DOCX · up to 10 MB'}</small></span></button>{file && <button type="button" className="remove-file" aria-label="Remove selected resume" disabled={busy} onClick={removeFile}><X size={15} /></button>}</div>
            </div>
            <div className="field-group role-group"><label className="field-label" htmlFor="target-role">Target role</label><input id="target-role" className="text-control" type="text" list="role-suggestions" autoComplete="off" disabled={busy} value={role} onChange={(event) => { setRole(event.target.value); if (review) { setReview(null); setNotice({ type: 'info', message: 'Role changed. Review the resume again to refresh the results.' }); } }} placeholder="Type a role, e.g. Data Analyst" /><datalist id="role-suggestions">{ROLE_SUGGESTIONS.map((suggestion) => <option value={suggestion} key={suggestion} />)}</datalist></div>
            <div className="field-group requirements-group"><label className="field-label" htmlFor="requirements">Job requirements <span>(optional)</span></label><textarea id="requirements" className="text-control requirements-control" disabled={busy} value={requirements} onChange={(event) => { setRequirements(event.target.value); if (review) { setReview(null); setNotice({ type: 'info', message: 'Requirements changed. Review the resume again to refresh the results.' }); } }} placeholder="Add key skills or paste a job description" rows="1" maxLength={20000} /></div>
            <button className="primary-button review-button" type="submit" disabled={busy}>{busy ? <><span className="spinner" />Reviewing</> : 'Review resume'}</button>
          </form>
          <div className="intake-foot"><span><LockKeyhole size={14} />Resume and extracted details stay in this session. Clear the review to remove them.</span><span className="format-note">Your file stays private</span></div>
          {notice && <div className={`notice notice-${notice.type}`} role={notice.type === 'error' ? 'alert' : 'status'}>{notice.type === 'error' ? <AlertCircle size={15} /> : notice.type === 'success' ? <Check size={15} /> : <Info size={15} />}<span>{notice.message}</span></div>}
        </section>

        {review ? (
          <section className="results-grid" aria-label="Resume analysis results" aria-live="polite">
            <article className="panel summary-panel">
              <div className="panel-heading"><div><p className="eyebrow">CANDIDATE PROFILE</p><h2>Resume summary</h2></div><button className="text-button" onClick={openEditor}><Pencil size={14} />Edit extracted details</button></div>
              {demoMode && <div className="demo-banner"><Info size={14} />Synthetic demo profile · fictional data for trying the dashboard</div>}
              <div className="profile-row"><span className="avatar profile-avatar">{initials}</span><div className="profile-main"><h3>{review.name}</h3><p>{review.role} <span className="dot-separator">·</span> {review.experience}</p></div><span className="parsed-tag"><Check size={13} />Extracted profile</span></div>
              <div className="facts-row"><div><span>Experience</span><strong>{review.experience}</strong></div><div><span>Recent role</span><strong>{review.role}</strong></div><div><span>Education</span><strong>{review.education}</strong></div><div><span>Location</span><strong>{review.location}</strong></div><div className="hidden-contact"><ShieldCheck size={14} /><span>Contact details hidden</span></div></div>
              <div className="section-heading-row"><div><h3>Skills and role evidence</h3><p>Skills found in the resume. Highlighted skills match this role’s criteria.</p></div>{!demoMode && <button className="quiet-button compact" onClick={() => setShowPreview(true)}><FileText size={14} />Preview resume</button>}</div>
              <div className="skill-review-hint">Confirm these detected skills for career suggestions. Toggle off anything the parser misread.</div>
              <div className="skill-chip-list" aria-label="Detected skills; toggle whether each should inform career suggestions">{review.skills.length ? review.skills.map((skill) => { const excluded = excludedCareerSkills.includes(skill.name); return <button type="button" key={skill.name} aria-pressed={!excluded} onClick={() => setExcludedCareerSkills((current) => excluded ? current.filter((name) => name !== skill.name) : [...current, skill.name])} className={`skill-chip skill-chip-toggle ${skill.role_match ? 'role-match' : ''} ${excluded ? 'skill-excluded' : ''}`} title={`${skill.mentions} mention(s); source: ${(skill.sources || []).join(', ') || 'not available'}`}>{!excluded && <Check size={11} />}{skill.name}<small>{(skill.sources || []).map((source) => source.replace('PDF · ', 'p. ').replace('DOCX · ', '')).join(', ')}</small></button>; }) : <p className="skills-empty">No skills from the current skill list were found in the extracted text.</p>}</div>
              <div className="profile-foot"><Info size={14} /><span>{review.extraction ? `${review.extraction.format} text extraction · ${review.extraction.characters.toLocaleString()} characters${review.extraction.ocr_pages ? ` · OCR on ${review.extraction.ocr_pages} page(s)` : ''}${review.extraction.warnings.length ? ` · ${review.extraction.warnings[0]}` : ''}. ` : ''}Skill source labels show page or document area only; resume text is not displayed. Confirm details against the original resume.</span></div>
            </article>

            <aside className="panel fit-panel">
              <div className="panel-heading fit-heading"><div><p className="eyebrow">ROLE COMPARISON</p><h2>Role fit overview</h2></div></div>
              <div className="fit-role"><span>Reviewing against</span><strong>{review.normalized_role || role.trim()}</strong></div>
              <div className="fit-score-row"><div><span className="fit-label">Evidence coverage</span><strong className="fit-score">{review.fit === null ? '—' : <>{review.fit}<small>%</small></>}</strong></div><span className="fit-status">{review.fit_status}</span></div>
              <div className={`progress-track ${review.fit === null ? 'is-empty' : ''}`} role="img" aria-label={review.fit === null ? 'Add criteria to calculate evidence coverage' : `${review.fit}% of listed criteria have matching resume text`}><span style={{ width: review.fit === null ? '0%' : `${review.fit}%` }} /></div>
              <p className="fit-description">{review.summary}</p>
              <div className="criteria-section"><div className="section-heading-row slim"><h3>Criteria to review</h3><span className="info-label" title="A text match shows that the resume mentions a criterion; it does not assess skill level."><Info size={14} /></span></div><ul className="criteria-list">{review.criteria.length ? review.criteria.map((criterion) => <li key={criterion.name}><span className={`criteria-dot ${criterion.found ? 'found' : 'open'}`}>{criterion.found ? <Check size={12} /> : <Info size={11} />}</span><span className="criterion-copy"><strong>{criterion.name}</strong><small>{criterion.status} · {criterion.detail}</small></span><span className="criterion-similarity">{criterion.similarity}%</span></li>) : <li className="criteria-empty">No role criteria available yet. Add requirements above to calculate evidence coverage.</li>}</ul></div>
              {reviewNote && <div className="saved-note"><div><span className="note-label">YOUR REVIEW NOTE</span><p>{reviewNote}</p></div><button className="note-remove" aria-label="Remove review note" onClick={() => setReviewNote('')}><X size={14} /></button></div>}
              <div className="fit-actions"><button className="secondary-button" onClick={() => { setNoteDraft(reviewNote); setShowNoteEditor(true); }}><Pencil size={14} />{reviewNote ? 'Edit review note' : 'Add review note'}</button><button className="quiet-button clear-button" onClick={clearReview}><RotateCcw size={14} />Clear results</button></div>
              <p className="fit-disclaimer">Fit reflects only information found in this resume and criteria provided.</p>
            </aside>
          </section>
        ) : (
          <section className="empty-state panel"><div className="empty-icon"><FileUp size={23} /></div><p className="eyebrow">READY WHEN YOU ARE</p><h2>Start with a resume and a role</h2><p>Upload a PDF or DOCX, enter a target role, and review extracted skills with evidence from the resume.</p><div className="empty-actions"><button className="primary-button" onClick={() => fileRef.current?.click()}><Upload size={15} />Choose a resume</button><button className="quiet-button" onClick={loadDemoReview} disabled={busy}>Try synthetic demo</button></div></section>
        )}

        {review && <section className="analytics-section" aria-label="Visual review metrics">
          <div className="analytics-heading"><div><p className="eyebrow">REVIEW VISUALS</p><h2>Evidence at a glance</h2><p>Text signals for this resume against the selected role criteria.</p></div><span className="analysis-method">TF-IDF · cosine similarity · decision rules</span></div>
          {criteria.length ? <div className="analytics-grid">
            <article className="panel chart-panel coverage-chart"><div className="chart-title"><div><h3>Requirement coverage</h3><p>Direct mentions, related passages, and criteria to check</p></div><Info size={15} /></div><div className="coverage-visual"><div className="donut-chart" style={{ '--found': `${matchedCount / criteria.length * 100}%`, '--related': `${relatedCount / criteria.length * 100}%` }}><div><strong>{review.fit ?? 0}%</strong><small>direct match</small></div></div><div className="chart-legend"><div><i className="legend-found" /><span>Direct mention</span><strong>{matchedCount}</strong></div><div><i className="legend-related" /><span>Related passage</span><strong>{relatedCount}</strong></div><div><i className="legend-missing" /><span>Needs review</span><strong>{missingCount}</strong></div></div></div></article>
            <article className="panel chart-panel similarity-chart"><div className="chart-title"><div><h3>Requirement text similarity</h3><p>TF-IDF compares each requirement with resume text; similarity is not a skill score</p></div><span className="chart-kpi">{averageSimilarity}%<small> avg.</small></span></div><div className="similarity-bars">{criteria.map((criterion) => <div className="similarity-row" key={criterion.name}><div className="similarity-label"><span>{criterion.name}</span><strong>{criterion.similarity}%</strong></div><div className="similarity-track"><span style={{ width: `${criterion.similarity}%` }} /></div></div>)}</div></article>
          </div> : <article className="panel analytics-empty"><Info size={16} /><span>Add job requirements or use a recognized role to generate matching charts and model signals.</span></article>}
        </section>}

        {review && <ModelRelevancePanel modelRelevance={review.model_summary.model_relevance} />}

        <BenchmarkSection benchmark={benchmark} />

        <section className="panel fairness-panel" id="fairness-guidance"><div className="fairness-title"><span className="fairness-icon"><Scale size={18} /></span><div><p className="eyebrow">RESPONSIBLE REVIEW</p><h2>Fairness & recruiter guidance</h2><p>Use consistent criteria and check evidence before comparing applicants.</p></div></div><div className="guidance-list"><div><span className="guidance-number">01</span><span>Apply the same role criteria to each applicant.</span></div><div><span className="guidance-number">02</span><span>Review extracted skills against the original resume before comparing results.</span></div><div><span className="guidance-number">03</span><span>Do not use protected traits or infer them from resume content.</span></div></div><div className="human-review-note"><Info size={16} /><p><strong>Human review is required.</strong><br />This tool supports a consistent review and does not predict hiring outcomes.</p></div></section>
        <CareerDirections directions={review?.career_directions} excludedSkills={excludedCareerSkills} />
        <footer className="page-footer"><span><LockKeyhole size={13} />Session-only processing · files are not saved</span><span>EquiHire <span className="footer-dot">·</span> Resume review prototype</span></footer>
      </main>

      {showHowItWorks && <Modal titleId="how-title" onClose={() => setShowHowItWorks(false)} className="how-modal"><div className="modal-heading"><div><p className="eyebrow">A QUICK GUIDE</p><h2 id="how-title">How it works</h2></div><button className="more-button" onClick={() => setShowHowItWorks(false)} aria-label="Close"><X size={18} /></button></div><ol className="how-steps"><li><span>01</span><div><strong>Upload a resume</strong><p>Choose a PDF or DOCX file up to 10 MB.</p></div></li><li><span>02</span><div><strong>Enter the target role</strong><p>Add a role and, if useful, paste key skills or a short job description.</p></div></li><li><span>03</span><div><strong>Review the evidence</strong><p>Check extracted details and the colored skill matches before making a decision.</p></div></li></ol><p className="how-note"><LockKeyhole size={14} />The file and analysis stay in this session and are discarded when cleared.</p><button className="primary-button how-done" onClick={() => setShowHowItWorks(false)}>Got it</button></Modal>}

      {showPreview && file && <Modal titleId="preview-title" onClose={() => setShowPreview(false)} className="preview-modal"><div className="modal-heading"><div><p className="eyebrow">SESSION FILE</p><h2 id="preview-title">Resume preview</h2><p className="modal-subtitle">{file.name} · {(file.size / 1024 / 1024).toFixed(2)} MB</p></div><button className="more-button" onClick={() => setShowPreview(false)} aria-label="Close preview"><X size={18} /></button></div>{previewUrl ? <iframe className="pdf-preview" src={previewUrl} title={`Preview of ${file.name}`} /> : <div className="docx-preview"><FileText size={30} /><strong>DOCX file selected</strong><p>Your browser does not display DOCX files inline. The document remains selected for this session.</p></div>}</Modal>}

      {showNoteEditor && <Modal titleId="note-title" onClose={() => setShowNoteEditor(false)} className="note-modal"><div className="modal-heading"><div><p className="eyebrow">SESSION ONLY</p><h2 id="note-title">Review note</h2></div><button className="more-button" onClick={() => setShowNoteEditor(false)} aria-label="Close"><X size={18} /></button></div><p className="modal-copy">Add a note for your own review. It is held in memory and cleared with this review.</p><form onSubmit={saveNote}><label className="field-label" htmlFor="review-note">Note</label><textarea id="review-note" className="text-control note-input" value={noteDraft} onChange={(event) => setNoteDraft(event.target.value)} placeholder="Add context or questions to follow up…" maxLength={500} autoFocus /><div className="modal-actions"><span className="character-count">{noteDraft.length}/500</span><button type="button" className="quiet-button" onClick={() => setShowNoteEditor(false)}>Cancel</button><button className="primary-button" type="submit">Save note</button></div></form></Modal>}

      {editing && editDraft && <Modal titleId="edit-title" onClose={() => setEditing(false)} className="edit-modal"><div className="modal-heading"><div><p className="eyebrow">CANDIDATE PROFILE</p><h2 id="edit-title">Edit extracted details</h2></div><button className="more-button" onClick={() => setEditing(false)} aria-label="Close"><X size={18} /></button></div><p className="modal-copy">Correct anything the parser may have misread. Changes stay in this session.</p><form className="edit-form" onSubmit={saveDetails}><label className="field-label" htmlFor="candidate-name">Candidate name</label><input id="candidate-name" className="text-control" value={editDraft.name} onChange={(event) => setEditDraft({ ...editDraft, name: event.target.value })} required /><label className="field-label" htmlFor="candidate-role">Recent role</label><input id="candidate-role" className="text-control" value={editDraft.role} onChange={(event) => setEditDraft({ ...editDraft, role: event.target.value })} /><div className="edit-grid"><div><label className="field-label" htmlFor="candidate-experience">Experience</label><input id="candidate-experience" className="text-control" value={editDraft.experience} onChange={(event) => setEditDraft({ ...editDraft, experience: event.target.value })} /></div><div><label className="field-label" htmlFor="candidate-location">Location</label><input id="candidate-location" className="text-control" value={editDraft.location} onChange={(event) => setEditDraft({ ...editDraft, location: event.target.value })} /></div></div><label className="field-label" htmlFor="candidate-education">Education</label><input id="candidate-education" className="text-control" value={editDraft.education} onChange={(event) => setEditDraft({ ...editDraft, education: event.target.value })} /><div className="modal-actions"><button type="button" className="quiet-button" onClick={() => setEditing(false)}>Cancel</button><button className="primary-button" type="submit">Save details</button></div></form></Modal>}
    </div>
  );
}

export default App;
