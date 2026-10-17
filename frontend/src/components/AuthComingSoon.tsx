'use client';

import { useEffect, useRef } from 'react';
import type { RefObject, MouseEvent } from 'react';
import Icon from './Icon';

export default function AuthComingSoon({ open, onClose, triggerRef, menuRef }: { open: boolean; onClose: () => void; triggerRef: RefObject<HTMLButtonElement>; menuRef: RefObject<HTMLButtonElement> }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const backdropPressRef = useRef(false);

  useEffect(() => {
    if (!open) return;
    const dialog = dialogRef.current;
    if (!dialog) return;
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

  const rememberBackdropPress = (event: MouseEvent<HTMLDialogElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    backdropPressRef.current = event.target === event.currentTarget && (
      event.clientX < bounds.left || event.clientX > bounds.right ||
      event.clientY < bounds.top || event.clientY > bounds.bottom
    );
  };

  const dismissBackdrop = (event: MouseEvent<HTMLDialogElement>) => {
    const startedOnBackdrop = backdropPressRef.current;
    backdropPressRef.current = false;
    if (!startedOnBackdrop || event.target !== event.currentTarget) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) onClose();
  };

  return <dialog ref={dialogRef} className={"auth-dialog w-[min(440px,_calc(100%_-_32px))] max-h-[calc(100svh_-_32px)] mt-[auto] mr-[auto] mb-[auto] ml-[auto] pt-[44px] pr-[36px] pb-[32px] pl-[36px] [border:1px_solid_var(--border-e1e5d9)] rounded-[23px] [background:var(--paper)] [color:var(--ink)] text-center [box-shadow:0_24px_90px_var(--shadow-142b3540)] overflow-auto [&::backdrop]:[background:var(--surface-122c4266)] [&::backdrop]:[backdrop-filter:blur(5px)] [&_.eyebrow]:text-[8px] [&_.eyebrow]:tracking-[1.4px] [&_.eyebrow]:[color:var(--text-849387)] [&_h2]:mt-[19px] [&_h2]:mr-[0] [&_h2]:mb-[17px] [&_h2]:ml-[0] [&_h2]:text-[clamp(30px,_6vw,_39px)] [&_h2]:tracking-[-1.5px] [&_h2]:leading-[1.2] [&_p]:[color:var(--text-6f7d73)] [&_p]:text-[14px] [&_p]:leading-[1.9] [&_p_span]:text-[12px] [&_p_span]:[color:var(--text-617067)] motion-safe:[&[open]]:[animation:auth-arrive_.22s_ease-out] max-[430.01px]:pl-[24px] max-[430.01px]:pr-[24px] dark:[&.auth-dialog]:[background:linear-gradient(145deg,#243329,#142219)] dark:[&.auth-dialog]:[border-color:#526d53] dark:[&.auth-dialog]:[box-shadow:0_32px_100px_#00000080,inset_0_1px_0_#ffffff0a] dark:[&.auth-dialog::backdrop]:[background:#030b08b3]"} aria-labelledby="auth-coming-soon-title" aria-describedby="auth-coming-soon-description" onCancel={(event) => { event.preventDefault(); onClose(); }} onMouseDown={rememberBackdropPress} onClick={dismissBackdrop}>
    <button className={"auth-dialog-close absolute top-[15px] right-[15px] inline-flex items-center justify-center w-[32px] h-[32px] rounded-[50%] [border:1px_solid_var(--line)] [background:transparent] [color:var(--text-728076)] [&:hover]:[background:var(--sage)]"} aria-label="Close coming soon message" onClick={onClose}><Icon name="close" size={18} /></button>
    <span className={"auth-dialog-symbol flex items-center justify-center w-[58px] h-[58px] mt-[0] mr-[auto] mb-[25px] ml-[auto] rounded-[50%] [background:var(--surface-e8eee4)] [color:var(--text-77928b)] [font-style:normal] [font-weight:normal] text-[36px] leading-[normal] [font-family:var(--serif)]"} aria-hidden="true">✳</span>
    <span className={"eyebrow block font-semibold leading-[1.6]"}>A LITTLE PATIENCE, A LITTLE MEANING.</span>
    <h2 id="auth-coming-soon-title">Thaam ja bhai <span className={"auth-dialog-emoji inline-block text-[.68em] align-[3px]"}>😄</span></h2>
    <p id="auth-coming-soon-description">Abhi thoda time lagega!<br /><span>Login aur signup coming soon.</span></p>
    <button className={"primary-button inline-flex items-center justify-center gap-[18px] min-h-[46px] pt-[12px] pr-[22px] pb-[12px] pl-[22px] rounded-[30px] text-[12px] [transition:background_.2s,_transform_.2s] [background:var(--ink)] [color:white] [border:1px_solid_var(--ink)] [&:hover]:[background:var(--surface-435947)] [&:hover]:[transform:translateY(-2px)] dark:[&.primary-button]:[color:var(--paper)] dark:[&.primary-button:hover]:[background:#c3d6c1] auth-dialog-dismiss mt-[27px] min-w-[155px]"} autoFocus onClick={onClose}>Theek hai <Icon name="arrow" size={17} /></button>
  </dialog>;
}
