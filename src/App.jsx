import { useEffect, useRef, useState } from 'react';
import {
  Bell, Check, CircleHelp, FileText, FileUp, Home, Info, LockKeyhole,
  Pencil, RotateCcw, Scale, ShieldCheck, Upload, X,
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

const navItems = [
  { label: 'Overview', href: '#top', icon: Home },
  { label: 'Resume review', href: '#resume-review', icon: FileText, active: true },
  { label: 'Fairness & guidance', href: '#fairness-guidance', icon: Scale },
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
  const [showNotifications, setShowNotifications] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [showNoteEditor, setShowNoteEditor] = useState(false);
  const [noteDraft, setNoteDraft] = useState('');
  const [reviewNote, setReviewNote] = useState('');

  useEffect(() => {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
      setPreviewUrl('');
      return undefined;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

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
    setReview(null);
    setReviewNote('');
    setNotice({ type: 'info', message: 'Resume ready. Add a target role, then choose Review resume.' });
  }

  function removeFile() {
    setFile(null);
    setReview(null);
    setReviewNote('');
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
      const apiBase = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
      const response = await fetch(`${apiBase}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: file.name,
          content_base64: contentBase64,
          target_role: role.trim(),
          job_requirements: requirements.trim(),
        }),
      });
      const result = await response.json();
      if (!response.ok) {
        const detail = Array.isArray(result.detail)
          ? result.detail.map((item) => item.msg).join(' ')
          : result.detail;
        throw new Error(detail || 'The resume could not be analyzed. Check the file and try again.');
      }
      setReview(result);
      setNotice({ type: 'info', message: 'Review complete. Check each excerpt in context; a mention does not confirm skill proficiency.' });
    } catch (error) {
      setReview(null);
      const message = error instanceof TypeError
        ? 'Could not reach the analysis service. Start the FastAPI server, then try again.'
        : error.message;
      setNotice({ type: 'error', message });
    } finally {
      setBusy(false);
    }
  }

  function clearReview() {
    setReview(null);
    setFile(null);
    setReviewNote('');
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

  const initials = review?.name.split(/\s+/).map((part) => part[0]).slice(0, 2).join('').toUpperCase() || 'MC';
  const criteria = review?.criteria || [];
  const matchedCount = criteria.filter((item) => item.found).length;
  const relatedCount = criteria.filter((item) => !item.found && item.similarity >= 12).length;
  const missingCount = Math.max(0, criteria.length - matchedCount - relatedCount);
  const averageSimilarity = criteria.length ? Math.round(criteria.reduce((sum, item) => sum + (item.similarity || 0), 0) / criteria.length) : 0;

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="EquiHire home"><span className="brand-mark"><i /><i /><i /></span><span>EquiHire</span></a>
        <div className="top-divider" />
        <nav className="main-nav" aria-label="Main navigation">
          {navItems.map(({ label, href, icon: Icon, active }) => <a className={active ? 'nav-link active' : 'nav-link'} href={href} key={label}><Icon size={16} strokeWidth={1.8} /><span>{label}</span></a>)}
        </nav>
        <div className="top-actions">
          <div className="notification-wrap"><button className="icon-button notification" aria-label="Notifications" aria-expanded={showNotifications} onClick={() => setShowNotifications((visible) => !visible)}><Bell size={18} /><span /></button>{showNotifications && <div className="notification-popover"><strong>You’re all caught up</strong><span>There are no new review updates.</span></div>}</div>
          <button className="quiet-button help-button header-help" onClick={() => setShowHowItWorks(true)}><CircleHelp size={16} />How it works</button>
        </div>
      </header>

      <main id="top" className="page-wrap">
        <section className="page-heading"><div><p className="eyebrow">CANDIDATE ASSESSMENT</p><h1>Resume review</h1><p className="subtitle">Review skills and role evidence from a resume.</p></div></section>

        <section className="intake-panel" id="resume-review" aria-label="Start a resume review">
          <form className="intake-form" onSubmit={runReview}>
            <div className="field-group upload-group">
              <label className="field-label" htmlFor="resume-upload">Resume</label>
              <input ref={fileRef} id="resume-upload" className="visually-hidden" type="file" disabled={busy} accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => chooseFile(event.target.files?.[0])} />
              <div className={`upload-control ${file ? 'has-file' : ''}`}><button className="upload-trigger" type="button" disabled={busy} onClick={() => fileRef.current?.click()}>{file ? <FileText size={19} /> : <Upload size={19} />}<span className="upload-copy"><strong>{file ? file.name : 'Upload resume'}</strong><small>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB · ready to review` : 'PDF or DOCX · up to 10 MB'}</small></span></button>{file && <button type="button" className="remove-file" aria-label="Remove selected resume" disabled={busy} onClick={removeFile}><X size={15} /></button>}</div>
            </div>
            <div className="field-group role-group"><label className="field-label" htmlFor="target-role">Target role</label><input id="target-role" className="text-control" type="text" disabled={busy} value={role} onChange={(event) => setRole(event.target.value)} placeholder="Type a role, e.g. Product Data Analyst" /></div>
            <div className="field-group requirements-group"><label className="field-label" htmlFor="requirements">Job requirements <span>(optional)</span></label><textarea id="requirements" className="text-control requirements-control" disabled={busy} value={requirements} onChange={(event) => setRequirements(event.target.value)} placeholder="Add key skills or paste a short job description" rows="1" /></div>
            <button className="primary-button review-button" type="submit" disabled={busy}>{busy ? <><span className="spinner" />Reviewing</> : 'Review resume'}</button>
          </form>
          <div className="intake-foot"><span><LockKeyhole size={14} />Resume and extracted details stay in this session. Clear the review to remove them.</span><span className="format-note">Your file stays private</span></div>
          {notice && <div className={`notice notice-${notice.type}`} role="status"><Info size={15} /><span>{notice.message}</span></div>}
        </section>

        {review ? (
          <section className="results-grid" aria-label="Resume analysis results" aria-live="polite">
            <article className="panel summary-panel">
              <div className="panel-heading"><div><p className="eyebrow">CANDIDATE PROFILE</p><h2>Resume summary</h2></div><button className="text-button" onClick={openEditor}><Pencil size={14} />Edit extracted details</button></div>
              <div className="profile-row"><span className="avatar profile-avatar">{initials}</span><div className="profile-main"><h3>{review.name}</h3><p>{review.role} <span className="dot-separator">·</span> {review.experience}</p></div><span className="parsed-tag"><Check size={13} />Extracted profile</span></div>
              <div className="facts-row"><div><span>Experience</span><strong>{review.experience}</strong></div><div><span>Recent role</span><strong>{review.role}</strong></div><div><span>Education</span><strong>{review.education}</strong></div><div><span>Location</span><strong>{review.location}</strong></div><div className="hidden-contact"><ShieldCheck size={14} /><span>Contact details hidden</span></div></div>
              <div className="section-heading-row"><div><h3>Skills and role evidence</h3><p>Skills found in the resume, with supporting context.</p></div><button className="quiet-button compact" onClick={() => setShowPreview(true)}><FileText size={14} />Preview resume</button></div>
              <div className="evidence-table-wrap"><table className="evidence-table"><thead><tr><th>Skill</th><th>Resume mention</th><th>Supporting excerpt</th><th>Source</th></tr></thead><tbody>{review.skills.length ? review.skills.map((skill) => <tr key={skill.name}><td className="skill-name">{skill.name}</td><td><span className="evidence-pill">{skill.evidence}</span></td><td className="excerpt">“{skill.excerpt}”</td><td className="page-ref">{skill.source}</td></tr>) : <tr><td className="empty-table" colSpan="4">No skills from the current skill list were found in the extracted text.</td></tr>}</tbody></table></div>
              <div className="profile-foot"><Info size={14} /><span>Extracted details may need correction. Review the resume evidence before using this summary.</span></div>
            </article>

            <aside className="panel fit-panel">
              <div className="panel-heading fit-heading"><div><p className="eyebrow">ROLE COMPARISON</p><h2>Role fit overview</h2></div></div>
              <div className="fit-role"><span>Reviewing against</span><strong>{role.trim()}</strong></div>
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
          <section className="empty-state panel"><div className="empty-icon"><FileUp size={23} /></div><p className="eyebrow">READY WHEN YOU ARE</p><h2>Start with a resume and a role</h2><p>Upload a PDF or DOCX, enter a target role, and review extracted skills with evidence from the resume.</p><button className="text-button" onClick={() => fileRef.current?.click()}><Upload size={15} />Choose a resume</button></section>
        )}

        {review && <section className="analytics-section" aria-label="Visual review metrics">
          <div className="analytics-heading"><div><p className="eyebrow">REVIEW VISUALS</p><h2>Evidence at a glance</h2><p>Text signals for this resume against the selected role criteria.</p></div><span className="analysis-method">TF-IDF · cosine similarity · decision rules</span></div>
          {criteria.length ? <div className="analytics-grid">
            <article className="panel chart-panel coverage-chart"><div className="chart-title"><div><h3>Requirement coverage</h3><p>Direct mentions, related passages, and criteria to check</p></div><Info size={15} /></div><div className="coverage-visual"><div className="donut-chart" style={{ '--found': `${matchedCount / criteria.length * 100}%`, '--related': `${relatedCount / criteria.length * 100}%` }}><div><strong>{review.fit ?? 0}%</strong><small>direct match</small></div></div><div className="chart-legend"><div><i className="legend-found" /><span>Direct mention</span><strong>{matchedCount}</strong></div><div><i className="legend-related" /><span>Related passage</span><strong>{relatedCount}</strong></div><div><i className="legend-missing" /><span>Needs review</span><strong>{missingCount}</strong></div></div></div></article>
            <article className="panel chart-panel similarity-chart"><div className="chart-title"><div><h3>Nearest resume evidence</h3><p>KNN ranks passages by TF-IDF similarity to each requirement</p></div><span className="chart-kpi">{averageSimilarity}%<small> avg.</small></span></div><div className="similarity-bars">{criteria.map((criterion) => <div className="similarity-row" key={criterion.name}><div className="similarity-label"><span>{criterion.name}</span><strong>{criterion.similarity}%</strong></div><div className="similarity-track"><span style={{ width: `${criterion.similarity}%` }} /></div></div>)}</div></article>
            <article className="panel model-panel"><div className="chart-title"><div><h3>Model-assisted review</h3><p>Transparent signals, with human verification</p></div></div><div className="model-cards"><div><span className="model-tag">KNN · TEXT SIMILARITY</span><strong>{averageSimilarity}%</strong><p>Average nearest-passage similarity across role criteria.</p></div><div><span className="model-tag">DECISION TREE · EVIDENCE TRIAGE</span><strong>{matchedCount} / {criteria.length}</strong><p>Direct mentions branch to repeated evidence, direct mention, related passage, or no clear evidence.</p></div></div><p className="model-caveat"><Info size={14} />These are evidence-matching signals, not skill proficiency or hiring predictions. Accuracy, precision, recall, and F1 need a labeled dataset and are not claimed here.</p></article>
          </div> : <article className="panel analytics-empty"><Info size={16} /><span>Add job requirements or use a recognized role to generate matching charts and model signals.</span></article>}
        </section>}

        <section className="panel fairness-panel" id="fairness-guidance"><div className="fairness-title"><span className="fairness-icon"><Scale size={18} /></span><div><p className="eyebrow">RESPONSIBLE REVIEW</p><h2>Fairness & recruiter guidance</h2><p>Use consistent criteria and check evidence before comparing applicants.</p></div></div><div className="guidance-list"><div><span className="guidance-number">01</span><span>Apply the same role criteria to each applicant.</span></div><div><span className="guidance-number">02</span><span>Review cited evidence and context before comparing scores.</span></div><div><span className="guidance-number">03</span><span>Do not use protected traits or infer them from resume content.</span></div></div><div className="human-review-note"><Info size={16} /><p><strong>Human review is required.</strong><br />This tool supports a consistent review and does not predict hiring outcomes.</p></div></section>
        <footer className="page-footer"><span><LockKeyhole size={13} />Session-only processing · files are not saved</span><span>EquiHire <span className="footer-dot">·</span> Resume review prototype</span></footer>
      </main>

      {showHowItWorks && <Modal titleId="how-title" onClose={() => setShowHowItWorks(false)} className="how-modal"><div className="modal-heading"><div><p className="eyebrow">A QUICK GUIDE</p><h2 id="how-title">How it works</h2></div><button className="more-button" onClick={() => setShowHowItWorks(false)} aria-label="Close"><X size={18} /></button></div><ol className="how-steps"><li><span>01</span><div><strong>Upload a resume</strong><p>Choose a PDF or DOCX file up to 10 MB.</p></div></li><li><span>02</span><div><strong>Enter the target role</strong><p>Add a role and, if useful, paste key skills or a short job description.</p></div></li><li><span>03</span><div><strong>Review the evidence</strong><p>Check extracted details, skill matches, and resume excerpts before making a decision.</p></div></li></ol><p className="how-note"><LockKeyhole size={14} />The file and analysis stay in this session and are discarded when cleared.</p><button className="primary-button how-done" onClick={() => setShowHowItWorks(false)}>Got it</button></Modal>}

      {showPreview && file && <Modal titleId="preview-title" onClose={() => setShowPreview(false)} className="preview-modal"><div className="modal-heading"><div><p className="eyebrow">SESSION FILE</p><h2 id="preview-title">Resume preview</h2><p className="modal-subtitle">{file.name} · {(file.size / 1024 / 1024).toFixed(2)} MB</p></div><button className="more-button" onClick={() => setShowPreview(false)} aria-label="Close preview"><X size={18} /></button></div>{previewUrl ? <iframe className="pdf-preview" src={previewUrl} title={`Preview of ${file.name}`} /> : <div className="docx-preview"><FileText size={30} /><strong>DOCX file selected</strong><p>Your browser does not display DOCX files inline. The document remains selected for this session.</p></div>}</Modal>}

      {showNoteEditor && <Modal titleId="note-title" onClose={() => setShowNoteEditor(false)} className="note-modal"><div className="modal-heading"><div><p className="eyebrow">SESSION ONLY</p><h2 id="note-title">Review note</h2></div><button className="more-button" onClick={() => setShowNoteEditor(false)} aria-label="Close"><X size={18} /></button></div><p className="modal-copy">Add a note for your own review. It is held in memory and cleared with this review.</p><form onSubmit={saveNote}><label className="field-label" htmlFor="review-note">Note</label><textarea id="review-note" className="text-control note-input" value={noteDraft} onChange={(event) => setNoteDraft(event.target.value)} placeholder="Add context or questions to follow up…" maxLength={500} autoFocus /><div className="modal-actions"><span className="character-count">{noteDraft.length}/500</span><button type="button" className="quiet-button" onClick={() => setShowNoteEditor(false)}>Cancel</button><button className="primary-button" type="submit">Save note</button></div></form></Modal>}

      {editing && editDraft && <Modal titleId="edit-title" onClose={() => setEditing(false)} className="edit-modal"><div className="modal-heading"><div><p className="eyebrow">CANDIDATE PROFILE</p><h2 id="edit-title">Edit extracted details</h2></div><button className="more-button" onClick={() => setEditing(false)} aria-label="Close"><X size={18} /></button></div><p className="modal-copy">Correct anything the parser may have misread. Changes stay in this session.</p><form className="edit-form" onSubmit={saveDetails}><label className="field-label" htmlFor="candidate-name">Candidate name</label><input id="candidate-name" className="text-control" value={editDraft.name} onChange={(event) => setEditDraft({ ...editDraft, name: event.target.value })} required /><label className="field-label" htmlFor="candidate-role">Recent role</label><input id="candidate-role" className="text-control" value={editDraft.role} onChange={(event) => setEditDraft({ ...editDraft, role: event.target.value })} /><div className="edit-grid"><div><label className="field-label" htmlFor="candidate-experience">Experience</label><input id="candidate-experience" className="text-control" value={editDraft.experience} onChange={(event) => setEditDraft({ ...editDraft, experience: event.target.value })} /></div><div><label className="field-label" htmlFor="candidate-location">Location</label><input id="candidate-location" className="text-control" value={editDraft.location} onChange={(event) => setEditDraft({ ...editDraft, location: event.target.value })} /></div></div><label className="field-label" htmlFor="candidate-education">Education</label><input id="candidate-education" className="text-control" value={editDraft.education} onChange={(event) => setEditDraft({ ...editDraft, education: event.target.value })} /><div className="modal-actions"><button type="button" className="quiet-button" onClick={() => setEditing(false)}>Cancel</button><button className="primary-button" type="submit">Save details</button></div></form></Modal>}
    </div>
  );
}

export default App;
