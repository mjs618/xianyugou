import { useCallback, useEffect, useRef } from 'react';
import { Modal } from 'antd';
import { useBlocker } from 'react-router-dom';

export interface UnsavedChangesState {
  dirty: boolean;
  submitting: boolean;
  allowNavigation: boolean;
}

export function shouldBlockNavigation({ dirty, submitting, allowNavigation }: UnsavedChangesState): boolean {
  return dirty && !submitting && !allowNavigation;
}

export function useUnsavedChanges({ dirty, submitting }: Omit<UnsavedChangesState, 'allowNavigation'>) {
  const allowNavigationRef = useRef(false);

  useEffect(() => {
    if (dirty) allowNavigationRef.current = false;
  }, [dirty]);

  const shouldBlock = useCallback(
    () => shouldBlockNavigation({ dirty, submitting, allowNavigation: allowNavigationRef.current }),
    [dirty, submitting],
  );
  const blocker = useBlocker(shouldBlock);

  useEffect(() => {
    if (blocker.state !== 'blocked') return;

    const instance = Modal.confirm({
      title: '有未保存的修改',
      content: '离开当前页面将丢失尚未保存的交易信息。',
      okText: '放弃修改',
      cancelText: '继续编辑',
      okButtonProps: { danger: true },
      onOk: () => blocker.proceed(),
      onCancel: () => blocker.reset(),
    });

    return () => instance.destroy();
  }, [blocker]);

  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!shouldBlock()) return;
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [shouldBlock]);

  return {
    allowNavigation: () => {
      allowNavigationRef.current = true;
    },
  };
}
