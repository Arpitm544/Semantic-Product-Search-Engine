'use client';

import { useEffect, useRef } from 'react';
import Icon from './Icon';

export default function AuthComingSoon({ open, onClose, triggerRef, menuRef }) {
  const dialogRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const dialog = dialogRef.current;
    const previousOverflow = document.body.style.overflow;
    dialog.showModal();
    document.body.style.overflow = 'hidden';
    return () => {
      dialog.close();
      document.body.style.overflow = previousOverflow;
      const trigger = triggerRef.current?.isConnected ? triggerRef.current : menuRef.current;
      trigger?.focus({ preventScroll: true });
    };
  }, [open, triggerRef, menuRef]);

  const dismissBackdrop = (event) => {
    if (event.target !== event.currentTarget) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) onClose();
  };

  return <dialog ref={dialogRef} className="auth-dialog" aria-labelledby="auth-coming-soon-title" aria-describedby="auth-coming-soon-description" onCancel={(event) => { event.preventDefault(); onClose(); }} onClick={dismissBackdrop}>
    <button className="auth-dialog-close" aria-label="Close coming soon message" onClick={onClose}><Icon name="close" size={18} /></button>
    <span className="auth-dialog-symbol" aria-hidden="true">✳</span>
    <span className="eyebrow">A LITTLE PATIENCE, A LITTLE MEANING.</span>
    <h2 id="auth-coming-soon-title">Thaam ja bhai <span className="auth-dialog-emoji">😄</span></h2>
    <p id="auth-coming-soon-description">Abhi thoda time lagega!<br /><span>Login aur signup coming soon.</span></p>
    <button className="primary-button auth-dialog-dismiss" autoFocus onClick={onClose}>Theek hai <Icon name="arrow" size={17} /></button>
  </dialog>;
}
