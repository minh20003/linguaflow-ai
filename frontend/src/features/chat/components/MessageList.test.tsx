import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MessageList } from './MessageList';
import type { ApiActionProposal } from '../api/chat-api';
import type { Conversation, Message, User } from '../types';

const scrollIntoView = vi.fn();

beforeEach(() => {
  // jsdom does not implement it, and the list calls it on the sentinel at the
  // foot of the thread. Spying on it is also how these tests observe whether
  // the viewport was moved at all.
  Object.defineProperty(Element.prototype, 'scrollIntoView', {
    configurable: true,
    value: scrollIntoView,
  });
  scrollIntoView.mockClear();
});

const currentUser: User = {
  id: 'me',
  email: 'me@example.com',
  name: 'Me',
  username: 'me',
  avatar: '',
  nativeLanguage: 'en',
  onlineStatus: 'online',
};

const conversation: Conversation = {
  id: 'conversation-1',
  type: 'direct',
  name: 'Alex',
  avatar: '',
  lastMessage: '',
  lastMessageTime: '10:00',
  unreadCount: 0,
};

function message(overrides: Partial<Message> = {}): Message {
  return {
    id: 'm1',
    senderId: 'alex',
    senderName: 'Alex',
    conversationId: conversation.id,
    content: 'Hello',
    messageType: 'text',
    transcriptionStatus: null,
    timestamp: '10:00',
    status: 'delivered',
    ...overrides,
  };
}

function proposal(overrides: Partial<ApiActionProposal> = {}): ApiActionProposal {
  return {
    id: 'proposal-1',
    conversation_id: conversation.id,
    source_message_id: 'm1',
    owner_user_id: currentUser.id,
    action_type: 'appointment',
    status: 'pending_confirmation',
    title: 'Họp review kiến trúc',
    details: null,
    location: null,
    scheduled_start_at: '2026-09-01T02:00:00Z',
    // Required since develop_v2 gave a proposal an end as well as a start.
    scheduled_end_at: null,
    due_at: null,
    clarification_prompt: null,
    clarification_question: null,
    confidence_score: 0.9,
    source_mode: 'proactive',
    created_at: '2026-08-29T02:00:00Z',
    missing_fields: '[]',
    ...overrides,
  };
}

function renderList(overrides: Partial<React.ComponentProps<typeof MessageList>> = {}) {
  const props: React.ComponentProps<typeof MessageList> = {
    messages: [message()],
    currentUser,
    conversation,
    onReact: vi.fn(),
    onReply: vi.fn(),
    onCopy: vi.fn(),
    onToggleOriginal: vi.fn(),
    onRetryTranslation: vi.fn(),
    onRetryTranscription: vi.fn(),
    retryingTranscriptionIds: new Set<string>(),
    onRateTranslation: vi.fn(),
    onEditTranslation: vi.fn(),
    onForward: vi.fn(),
    onSaveMessage: vi.fn(),
    onDeleteMessage: vi.fn(),
    onDownloadAttachment: vi.fn(),
    onLoadAttachmentPreview: vi.fn().mockResolvedValue(''),
    language: 'en',
    // The chat card follows the translation language, not the chrome.
    contentLanguage: 'en' as const,
    ...overrides,
  };
  const view = render(<MessageList {...props} />);
  const rerenderWith = (patch: Partial<React.ComponentProps<typeof MessageList>>) =>
    view.rerender(<MessageList {...props} {...patch} />);
  return { ...view, props, rerenderWith };
}

/** Put the reader `distance` pixels above the foot, the way scrolling would. */
function scrollAwayFromFoot(distance = 3100) {
  const container = document.getElementById('chat-messages-container')!;
  Object.defineProperty(container, 'scrollHeight', { configurable: true, value: 4000 });
  Object.defineProperty(container, 'clientHeight', { configurable: true, value: 600 });
  Object.defineProperty(container, 'scrollTop', {
    configurable: true,
    writable: true,
    value: 4000 - 600 - distance,
  });
  fireEvent.scroll(container);
  return container;
}

describe('following the foot of a thread', () => {
  it('leaves the viewport alone when an existing message is rewritten in place', () => {
    const { rerenderWith } = renderList({ messages: [message(), message({ id: 'm2' })] });
    scrollAwayFromFoot();
    scrollIntoView.mockClear();

    // A reaction, a "show original" toggle or an arriving translation all
    // replace the array without adding anything to it.
    rerenderWith({ messages: [message({ content: 'Hello!' }), message({ id: 'm2' })] });

    expect(scrollIntoView).not.toHaveBeenCalled();
  });

  it('offers the trip back rather than taking it when a message arrives further up the thread', () => {
    const { rerenderWith } = renderList({ messages: [message()] });
    scrollAwayFromFoot();
    scrollIntoView.mockClear();

    rerenderWith({ messages: [message(), message({ id: 'm2', content: 'Are you there?' })] });

    expect(scrollIntoView).not.toHaveBeenCalled();
    const jump = screen.getByRole('button', { name: 'Jump to the latest message' });
    fireEvent.click(jump);
    expect(scrollIntoView).toHaveBeenCalled();
  });

  it('stops following after a nudge of the wheel without putting an arrow on screen', () => {
    const { rerenderWith } = renderList({ messages: [message()] });
    scrollAwayFromFoot(200);
    scrollIntoView.mockClear();

    expect(screen.queryByRole('button', { name: 'Jump to the latest message' })).toBeNull();

    // Something arriving there is still worth an arrow — the reader is no
    // longer at the foot, so nothing would tell them otherwise.
    rerenderWith({ messages: [message(), message({ id: 'm2', content: 'Are you there?' })] });

    expect(scrollIntoView).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Jump to the latest message' })).toBeTruthy();
  });

  it('follows an arriving message while the reader is still at the foot', () => {
    const { rerenderWith } = renderList({ messages: [message()] });
    scrollIntoView.mockClear();

    rerenderWith({ messages: [message(), message({ id: 'm2', content: 'Are you there?' })] });

    expect(scrollIntoView).toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: 'Jump to the latest message' })).toBeNull();
  });
});

describe('the assistant proposing an action inside the conversation', () => {
  it('places the card under the message the proposal was extracted from', () => {
    renderList({
      messages: [message(), message({ id: 'm2', content: 'Sure' })],
      proposals: [proposal()],
      onApproveProposal: vi.fn(),
      onRejectProposal: vi.fn(),
    });

    const card = screen.getByText('Trợ lý đề xuất thêm vào lịch');
    const source = document.getElementById('message-m1')!;
    const later = document.getElementById('message-m2')!;
    expect(source.compareDocumentPosition(card) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(later.compareDocumentPosition(card) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();
  });

  it('says the event was added once the proposal is approved', () => {
    const { rerenderWith } = renderList({
      proposals: [proposal()],
      onApproveProposal: vi.fn(),
      onRejectProposal: vi.fn(),
    });

    rerenderWith({ proposals: [proposal({ status: 'confirmed' })] });

    // The fixture renders with language "en", so the card answers in English.
    expect(
      screen.getByText(/Added to your personal calendar: "Họp review kiến trúc"/),
    ).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Duyệt và thêm vào lịch/ })).toBeNull();
  });

  it('says the proposal was turned down once it is rejected', () => {
    const { rerenderWith } = renderList({
      proposals: [proposal()],
      onApproveProposal: vi.fn(),
      onRejectProposal: vi.fn(),
    });

    rerenderWith({ proposals: [proposal({ status: 'rejected' })] });

    expect(
      screen.getByText(/Turned down, and left off your calendar: "Họp review kiến trúc"/),
    ).toBeTruthy();
  });
});
