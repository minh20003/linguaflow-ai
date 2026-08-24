import React, { useState, useMemo } from 'react';
import {
  BookOpen,
  Plus,
  Search,
  Filter,
  Download,
  Upload,
  Trash2,
  Edit2,
  Tag,
  Copy,
  Check,
  X
} from 'lucide-react';
import { TermItem, TermCategory, LanguageCode } from '../../types';

interface GlossaryViewProps {
  terms: TermItem[];
  onAddTerm: (term: Omit<TermItem, 'id' | 'createdAt' | 'updatedAt' | 'usageCount'>) => Promise<void>;
  onUpdateTerm: (id: string, updatedData: Partial<TermItem>) => Promise<void>;
  onDeleteTerm: (id: string) => Promise<void>;
  onBatchImport: (importedTerms: Omit<TermItem, 'id' | 'createdAt' | 'updatedAt' | 'usageCount'>[]) => Promise<void>;
  onNotify: (message: string, type?: 'success' | 'info' | 'error') => void;
}

const CATEGORIES: TermCategory[] = [
  'Công nghệ & AI',
  'Kinh doanh & Tài chính',
  'UI/UX & Sản phẩm',
  'Pháp lý & Điều khoản',
  'Y tế & Sức khỏe',
  'Giao tiếp hàng ngày',
];

export const GlossaryView: React.FC<GlossaryViewProps> = ({
  terms,
  onAddTerm,
  onUpdateTerm,
  onDeleteTerm,
  onBatchImport,
  onNotify,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedLanguage, setSelectedLanguage] = useState<string>('all');
  const [selectedPriority, setSelectedPriority] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');

  // Modals state
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [editingTerm, setEditingTerm] = useState<TermItem | null>(null);
  const [deletingTermId, setDeletingTermId] = useState<string | null>(null);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [importText, setImportText] = useState('');
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Form State for Add / Edit
  const [formData, setFormData] = useState({
    sourceTerm: '',
    targetTerm: '',
    sourceLang: 'EN' as LanguageCode,
    targetLang: 'VI' as LanguageCode,
    category: 'Công nghệ & AI' as TermCategory,
    priority: 'Bắt buộc (High)' as 'Bắt buộc (High)' | 'Khuyên dùng (Medium)' | 'Tham khảo (Low)',
    isStrict: false,
    notes: '',
    status: 'active' as 'active' | 'inactive',
  });

  // Filtered terms
  const filteredTerms = useMemo(() => {
    return terms.filter((item) => {
      const matchSearch =
        item.sourceTerm.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.targetTerm.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (item.notes && item.notes.toLowerCase().includes(searchTerm.toLowerCase()));

      const matchCategory = selectedCategory === 'all' || item.category === selectedCategory;
      const matchLang =
        selectedLanguage === 'all' ||
        `${item.sourceLang} → ${item.targetLang}` === selectedLanguage;
      const matchPriority = selectedPriority === 'all' || item.priority.includes(selectedPriority);
      const matchStatus = selectedStatus === 'all' || item.status === selectedStatus;

      return matchSearch && matchCategory && matchLang && matchPriority && matchStatus;
    });
  }, [terms, searchTerm, selectedCategory, selectedLanguage, selectedPriority, selectedStatus]);

  // Statistics calculation
  const totalTerms = terms.length;
  const activeTermsCount = terms.filter((t) => t.status === 'active').length;
  const highPriorityCount = terms.filter((t) => t.priority.includes('High')).length;
  const totalAppliedUsage = terms.reduce((acc, curr) => acc + (curr.usageCount || 0), 0);

  // Handlers
  const handleOpenAddModal = () => {
    setFormData({
      sourceTerm: '',
      targetTerm: '',
      sourceLang: 'EN',
      targetLang: 'VI',
      category: 'Công nghệ & AI',
      priority: 'Bắt buộc (High)',
      isStrict: false,
      notes: '',
      status: 'active',
    });
    setIsAddModalOpen(true);
  };

  const handleOpenEditModal = (term: TermItem) => {
    setEditingTerm(term);
    setFormData({
      sourceTerm: term.sourceTerm,
      targetTerm: term.targetTerm,
      sourceLang: term.sourceLang,
      targetLang: term.targetLang,
      category: term.category,
      priority: term.priority,
      isStrict: term.isStrict,
      notes: term.notes || '',
      status: term.status,
    });
  };

  const handleSubmitForm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.sourceTerm.trim() || !formData.targetTerm.trim()) {
      onNotify('Vui lòng nhập cả thuật ngữ gốc và bản dịch chuẩn', 'error');
      return;
    }

    if (editingTerm) {
      try {
        await onUpdateTerm(editingTerm.id, { ...formData, updatedAt: new Date().toISOString().split('T')[0] });
        onNotify(`Đã cập nhật thuật ngữ "${formData.sourceTerm}"`, 'success');
        setEditingTerm(null);
      } catch {
        onNotify('Không thể cập nhật thuật ngữ trên máy chủ.', 'error');
      }
    } else {
      try {
        await onAddTerm({ ...formData, createdBy: 'admin@linguaflow.ai' });
        onNotify(`Đã thêm thuật ngữ "${formData.sourceTerm}" vào từ điển`, 'success');
        setIsAddModalOpen(false);
      } catch {
        onNotify('Không thể thêm thuật ngữ trên máy chủ.', 'error');
      }
    }
  };

  const handleConfirmDelete = async () => {
    if (deletingTermId) {
      const termToDelete = terms.find((t) => t.id === deletingTermId);
      try {
        await onDeleteTerm(deletingTermId);
        onNotify(`Đã ngừng áp dụng thuật ngữ "${termToDelete?.sourceTerm}"`, 'info');
        setDeletingTermId(null);
      } catch {
        onNotify('Không thể cập nhật trạng thái thuật ngữ trên máy chủ.', 'error');
      }
    }
  };

  const handleExportCSV = () => {
    const headers = ['Source Term', 'Target Translation', 'Source Lang', 'Target Lang', 'Category', 'Priority', 'Strict Match', 'Status', 'Usage Count', 'Notes'];
    const rows = filteredTerms.map((t) => [
      `"${t.sourceTerm.replace(/"/g, '""')}"`,
      `"${t.targetTerm.replace(/"/g, '""')}"`,
      t.sourceLang,
      t.targetLang,
      `"${t.category}"`,
      `"${t.priority}"`,
      t.isStrict ? 'Yes' : 'No',
      t.status,
      t.usageCount,
      `"${(t.notes || '').replace(/"/g, '""')}"`,
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,\uFEFF' + [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `linguaflow-glossary-${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    onNotify(`Đã xuất ${filteredTerms.length} thuật ngữ ra file CSV thành công!`, 'success');
  };

  const handleProcessImport = async () => {
    if (!importText.trim()) {
      onNotify('Vui lòng dán nội dung CSV hoặc JSON để import', 'error');
      return;
    }

    try {
      const parsedItems: Omit<TermItem, 'id' | 'createdAt' | 'updatedAt' | 'usageCount'>[] = [];

      // Check if JSON
      if (importText.trim().startsWith('[') || importText.trim().startsWith('{')) {
        const jsonData = JSON.parse(importText);
        const arrayData = Array.isArray(jsonData) ? jsonData : [jsonData];
        for (const item of arrayData) {
          if (item.sourceTerm && item.targetTerm) {
            parsedItems.push({
              sourceTerm: item.sourceTerm,
              targetTerm: item.targetTerm,
              sourceLang: item.sourceLang || 'EN',
              targetLang: item.targetLang || 'VI',
              category: item.category || 'Công nghệ & AI',
              priority: item.priority || 'Bắt buộc (High)',
              isStrict: Boolean(item.isStrict),
              notes: item.notes || '',
              status: item.status || 'active',
              createdBy: 'import@linguaflow.ai',
            });
          }
        }
      } else {
        // Parse CSV lines
        const lines = importText.trim().split('\n');
        for (let i = 0; i < lines.length; i++) {
          const line = lines[i].trim();
          if (!line || (i === 0 && line.toLowerCase().includes('source'))) continue; // skip header
          const cols = line.split(',').map((c) => c.replace(/^["']|["']$/g, '').trim());
          if (cols.length >= 2 && cols[0] && cols[1]) {
            parsedItems.push({
              sourceTerm: cols[0],
              targetTerm: cols[1],
              sourceLang: (cols[2] as LanguageCode) || 'EN',
              targetLang: (cols[3] as LanguageCode) || 'VI',
              category: (cols[4] as TermCategory) || 'Công nghệ & AI',
              priority: (cols[5] as TermItem['priority']) || 'Bắt buộc (High)',
              isStrict: cols[6]?.toLowerCase() === 'yes' || cols[6] === 'true',
              notes: cols[9] || cols[7] || '',
              status: cols[7]?.toLowerCase() === 'inactive' ? 'inactive' : 'active',
              createdBy: 'import@linguaflow.ai',
            });
          }
        }
      }

      if (parsedItems.length === 0) {
        onNotify('Không tìm thấy dòng dữ liệu hợp lệ nào. Vui lòng kiểm tra định dạng.', 'error');
        return;
      }

      await onBatchImport(parsedItems);
      onNotify(`Đã nhập thành công ${parsedItems.length} thuật ngữ vào từ điển!`, 'success');
      setIsImportModalOpen(false);
      setImportText('');
    } catch {
      onNotify('Lỗi cú pháp khi đọc dữ liệu import. Vui lòng kiểm tra lại định dạng JSON/CSV.', 'error');
    }
  };

  const handleCopyTerm = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Top Stats Ribbon */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-xs flex flex-col justify-between">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider block">Tổng thuật ngữ</span>
          <div className="mt-2 text-2xl font-bold text-gray-900 tracking-tight">{totalTerms}</div>
          <div className="mt-2 text-xs text-gray-400 font-medium">Toàn bộ kho từ điển</div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-xs flex flex-col justify-between">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider block">Đang áp dụng</span>
          <div className="mt-2 text-2xl font-bold text-gray-900 tracking-tight">{activeTermsCount}</div>
          <div className="mt-2 text-xs text-green-600 font-medium">Được AI nạp vào context</div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-xs flex flex-col justify-between">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider block">Ưu tiên bắt buộc</span>
          <div className="mt-2 text-2xl font-bold text-gray-900 tracking-tight">{highPriorityCount}</div>
          <div className="mt-2 text-xs text-blue-600 font-medium">Quy tắc chuẩn tuyệt đối</div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-xs flex flex-col justify-between">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider block">Lượt áp dụng thực tế</span>
          <div className="mt-2 text-2xl font-bold text-gray-900 tracking-tight">{totalAppliedUsage}</div>
          <div className="mt-2 text-xs text-gray-500 font-medium">Lượt khớp trong các phiên dịch</div>
        </div>
      </div>

      {/* Control Bar: Search & Action Buttons */}
      <div className="bg-white rounded-xl p-5 border border-gray-200 shadow-xs space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Search Box */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              id="input-glossary-search"
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Tìm kiếm theo thuật ngữ gốc, bản dịch hoặc ghi chú..."
              className="w-full pl-9 pr-4 py-2 text-xs sm:text-sm bg-white border border-gray-300 rounded-md focus:border-blue-600 outline-hidden transition-colors"
            />
          </div>

          {/* Action Buttons: Add, Import, Export */}
          <div className="flex items-center gap-2 shrink-0">
            <button
              id="btn-import-glossary"
              onClick={() => setIsImportModalOpen(true)}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-gray-700 bg-white hover:bg-gray-50 border border-gray-300 rounded-md transition-colors"
            >
              <Upload className="w-3.5 h-3.5" />
              <span>Import</span>
            </button>

            <button
              id="btn-export-glossary"
              onClick={handleExportCSV}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-gray-700 bg-white hover:bg-gray-50 border border-gray-300 rounded-md transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export CSV</span>
            </button>

            <button
              id="btn-add-new-term"
              onClick={handleOpenAddModal}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs sm:text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md shadow-xs transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>Thêm thuật ngữ</span>
            </button>
          </div>
        </div>

        {/* Filter Badges */}
        <div className="flex flex-wrap items-center gap-2 pt-3 border-t border-gray-100 text-xs">
          <div className="flex items-center gap-1 text-gray-500 font-medium mr-1">
            <Filter className="w-3.5 h-3.5" />
            <span>Bộ lọc:</span>
          </div>

          {/* Category Filter */}
          <select
            id="filter-glossary-category"
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="py-1 px-2.5 bg-white border border-gray-300 rounded-md text-gray-700 font-medium outline-hidden hover:bg-gray-50"
          >
            <option value="all">Tất cả chuyên ngành</option>
            {CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>

          {/* Language Pair Filter */}
          <select
            id="filter-glossary-lang"
            value={selectedLanguage}
            onChange={(e) => setSelectedLanguage(e.target.value)}
            className="py-1 px-2.5 bg-white border border-gray-300 rounded-md text-gray-700 font-medium outline-hidden hover:bg-gray-50"
          >
            <option value="all">Tất cả cặp ngôn ngữ</option>
            <option value="EN → VI">EN → VI</option>
            <option value="VI → EN">VI → EN</option>
          </select>

          {/* Priority Filter */}
          <select
            id="filter-glossary-priority"
            value={selectedPriority}
            onChange={(e) => setSelectedPriority(e.target.value)}
            className="py-1 px-2.5 bg-white border border-gray-300 rounded-md text-gray-700 font-medium outline-hidden hover:bg-gray-50"
          >
            <option value="all">Mọi mức độ ưu tiên</option>
            <option value="High">Bắt buộc (High)</option>
            <option value="Medium">Khuyên dùng (Medium)</option>
            <option value="Low">Tham khảo (Low)</option>
          </select>

          {/* Status Filter */}
          <select
            id="filter-glossary-status"
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="py-1 px-2.5 bg-white border border-gray-300 rounded-md text-gray-700 font-medium outline-hidden hover:bg-gray-50"
          >
            <option value="all">Tất cả trạng thái</option>
            <option value="active">Đang áp dụng</option>
            <option value="inactive">Tạm ngưng</option>
          </select>

          {(selectedCategory !== 'all' ||
            selectedLanguage !== 'all' ||
            selectedPriority !== 'all' ||
            selectedStatus !== 'all' ||
            searchTerm) && (
            <button
              onClick={() => {
                setSelectedCategory('all');
                setSelectedLanguage('all');
                setSelectedPriority('all');
                setSelectedStatus('all');
                setSearchTerm('');
              }}
              className="text-blue-600 hover:text-blue-800 text-xs font-medium ml-auto"
            >
              Đặt lại bộ lọc
            </button>
          )}
        </div>
      </div>

      {/* Terms Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
        {filteredTerms.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <div className="w-10 h-10 rounded-full bg-gray-100 text-gray-400 mx-auto flex items-center justify-center">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-900">Không tìm thấy thuật ngữ phù hợp</p>
              <p className="text-xs text-gray-500 mt-1 max-w-sm mx-auto">
                Hãy thử thay đổi từ khóa tìm kiếm hoặc điều chỉnh lại các bộ lọc chuyên ngành.
              </p>
            </div>
            <button
              onClick={handleOpenAddModal}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-blue-600 text-white rounded-md text-xs font-medium hover:bg-blue-700"
            >
              <Plus className="w-3.5 h-3.5" /> Thêm thuật ngữ mới
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-gray-50 text-[11px] text-gray-400 uppercase font-bold tracking-wider border-b border-gray-100">
                <tr>
                  <th className="px-6 py-3">Thuật ngữ gốc (Source)</th>
                  <th className="px-6 py-3">Bản dịch chuẩn (Canonical)</th>
                  <th className="px-6 py-3">Cặp</th>
                  <th className="px-6 py-3">Chuyên ngành</th>
                  <th className="px-6 py-3">Ưu tiên</th>
                  <th className="px-6 py-3 text-center">Trạng thái</th>
                  <th className="px-6 py-3 text-right">Lượt dùng</th>
                  <th className="px-6 py-3 text-center">Thao tác</th>
                </tr>
              </thead>
              <tbody className="text-sm divide-y divide-gray-100 text-gray-700">
                {filteredTerms.map((term) => (
                  <tr key={term.id} className="hover:bg-gray-50/60 transition-colors group">
                    {/* Source Term */}
                    <td className="px-6 py-3.5 font-medium text-gray-900">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-sm">{term.sourceTerm}</span>
                        {term.isStrict && (
                          <span
                            className="text-[10px] px-1.5 py-0.2 rounded bg-gray-100 text-gray-700 font-semibold"
                            title="Khớp chính xác từng chữ hoa/thường"
                          >
                            Strict
                          </span>
                        )}
                        <button
                          onClick={() => handleCopyTerm(term.id, term.sourceTerm)}
                          title="Sao chép"
                          className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-gray-700 p-0.5 transition-opacity"
                        >
                          {copiedId === term.id ? (
                            <Check className="w-3 h-3 text-green-600" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                        </button>
                      </div>
                      {term.notes && (
                        <p className="text-xs text-gray-400 font-normal mt-0.5 line-clamp-1">
                          {term.notes}
                        </p>
                      )}
                    </td>

                    {/* Target Translation */}
                    <td className="px-6 py-3.5 font-medium text-blue-700">
                      <div className="text-sm text-gray-900 font-medium">{term.targetTerm}</div>
                    </td>

                    {/* Pair */}
                    <td className="px-6 py-3.5 whitespace-nowrap">
                      <span className="font-mono text-xs font-medium px-2 py-0.5 rounded bg-gray-100 text-gray-700">
                        {term.sourceLang} → {term.targetLang}
                      </span>
                    </td>

                    {/* Domain / Category */}
                    <td className="px-6 py-3.5 whitespace-nowrap">
                      <span className="inline-flex items-center gap-1 text-xs text-gray-600">
                        <Tag className="w-3 h-3 text-gray-400" />
                        {term.category}
                      </span>
                    </td>

                    {/* Priority */}
                    <td className="px-6 py-3.5 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                          term.priority.includes('High')
                            ? 'bg-rose-50 text-rose-700 border border-rose-200'
                            : term.priority.includes('Medium')
                            ? 'bg-amber-50 text-amber-700 border border-amber-200'
                            : 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {term.priority}
                      </span>
                    </td>

                    {/* Status */}
                    <td className="px-6 py-3.5 text-center whitespace-nowrap">
                      <button
                        onClick={() => {
                          void onUpdateTerm(term.id, {
                            status: term.status === 'active' ? 'inactive' : 'active',
                          }).catch(() => onNotify('Không thể đổi trạng thái thuật ngữ trên máy chủ.', 'error'));
                        }}
                        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium transition-colors ${
                          term.status === 'active'
                            ? 'bg-green-50 text-green-700 hover:bg-green-100'
                            : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                        }`}
                        title="Nhấp để chuyển trạng thái"
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            term.status === 'active' ? 'bg-green-500' : 'bg-gray-400'
                          }`}
                        />
                        {term.status === 'active' ? 'Hoạt động' : 'Tạm dừng'}
                      </button>
                    </td>

                    {/* Usage Count */}
                    <td className="px-6 py-3.5 text-right font-mono text-gray-700 whitespace-nowrap">
                      {term.usageCount} <span className="text-gray-400 font-normal text-xs">lần</span>
                    </td>

                    {/* Actions */}
                    <td className="px-6 py-3.5 text-center whitespace-nowrap">
                      <div className="inline-flex items-center gap-1">
                        <button
                          id={`btn-edit-term-${term.id}`}
                          onClick={() => handleOpenEditModal(term)}
                          className="p-1.5 text-gray-500 hover:text-blue-600 hover:bg-gray-100 rounded transition-colors"
                          title="Chỉnh sửa thuật ngữ"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          id={`btn-delete-term-${term.id}`}
                          onClick={() => setDeletingTermId(term.id)}
                          className="p-1.5 text-gray-500 hover:text-rose-600 hover:bg-gray-100 rounded transition-colors"
                          title="Xóa thuật ngữ"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add / Edit Term Modal */}
      {(isAddModalOpen || editingTerm) && (
        <div
          id="term-form-modal"
          className="fixed inset-0 bg-gray-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4"
          onClick={() => {
            setIsAddModalOpen(false);
            setEditingTerm(null);
          }}
        >
          <div
            className="bg-white rounded-xl max-w-lg w-full p-6 shadow-lg border border-gray-200 space-y-4 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div>
                <h3 className="font-semibold text-gray-900 text-base">
                  {editingTerm ? 'Chỉnh sửa Thuật ngữ' : 'Thêm Thuật ngữ Mới'}
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  Quy chuẩn hóa bản dịch chính xác cho AI LinguaFlow
                </p>
              </div>
              <button
                onClick={() => {
                  setIsAddModalOpen(false);
                  setEditingTerm(null);
                }}
                className="text-gray-400 hover:text-gray-700 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSubmitForm} className="space-y-4 text-xs">
              {/* Language Pair Selector */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-gray-700 mb-1">Ngôn ngữ nguồn</label>
                  <select
                    value={formData.sourceLang}
                    onChange={(e) =>
                      setFormData({ ...formData, sourceLang: e.target.value as LanguageCode })
                    }
                    className="w-full p-2 bg-white border border-gray-300 rounded-md outline-hidden focus:border-blue-600 text-gray-900 font-medium"
                  >
                    <option value="EN">English (EN)</option>
                    <option value="VI">Tiếng Việt (VI)</option>
                    <option value="JA">Japanese (JA)</option>
                  </select>
                </div>
                <div>
                  <label className="block font-medium text-gray-700 mb-1">Ngôn ngữ đích</label>
                  <select
                    value={formData.targetLang}
                    onChange={(e) =>
                      setFormData({ ...formData, targetLang: e.target.value as LanguageCode })
                    }
                    className="w-full p-2 bg-white border border-gray-300 rounded-md outline-hidden focus:border-blue-600 text-gray-900 font-medium"
                  >
                    <option value="VI">Tiếng Việt (VI)</option>
                    <option value="EN">English (EN)</option>
                    <option value="JA">Japanese (JA)</option>
                  </select>
                </div>
              </div>

              {/* Source Term Input */}
              <div>
                <label className="block font-medium text-gray-700 mb-1">
                  Thuật ngữ gốc <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={formData.sourceTerm}
                  onChange={(e) => setFormData({ ...formData, sourceTerm: e.target.value })}
                  placeholder="Ví dụ: Zero-shot inference, Rate limiting..."
                  className="w-full p-2 bg-white border border-gray-300 rounded-md outline-hidden focus:border-blue-600 text-gray-900 font-medium"
                />
              </div>

              {/* Target Translation Input */}
              <div>
                <label className="block font-medium text-gray-700 mb-1">
                  Bản dịch quy chuẩn <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={formData.targetTerm}
                  onChange={(e) => setFormData({ ...formData, targetTerm: e.target.value })}
                  placeholder="Ví dụ: Suy luận zero-shot, Giới hạn tần suất..."
                  className="w-full p-2 bg-white border border-gray-300 rounded-md outline-hidden focus:border-blue-600 text-gray-900 font-medium"
                />
              </div>

              {/* Category & Priority */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-gray-700 mb-1">Chuyên ngành</label>
                  <select
                    value={formData.category}
                    onChange={(e) =>
                      setFormData({ ...formData, category: e.target.value as TermCategory })
                    }
                    className="w-full p-2 bg-white border border-gray-300 rounded-md outline-hidden focus:border-blue-600 text-gray-900 font-medium"
                  >
                    {CATEGORIES.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block font-medium text-gray-700 mb-1">Mức độ ưu tiên</label>
                  <select
                    value={formData.priority}
                    onChange={(e) => setFormData({ ...formData, priority: e.target.value as TermItem['priority'] })}
                    className="w-full p-2 bg-white border border-gray-300 rounded-md outline-hidden focus:border-blue-600 text-gray-900 font-medium"
                  >
                    <option value="Bắt buộc (High)">Bắt buộc (High)</option>
                    <option value="Khuyên dùng (Medium)">Khuyên dùng (Medium)</option>
                    <option value="Tham khảo (Low)">Tham khảo (Low)</option>
                  </select>
                </div>
              </div>

              {/* Notes */}
              <div>
                <label className="block font-medium text-gray-700 mb-1">
                  Ghi chú ngữ cảnh & hướng dẫn dịch
                </label>
                <textarea
                  rows={2}
                  value={formData.notes}
                  onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                  placeholder="Ví dụ: Giữ nguyên từ mượn trong bài báo công nghệ, không dịch thô..."
                  className="w-full p-2 bg-white border border-gray-300 rounded-md outline-hidden focus:border-blue-600 text-gray-900 font-medium"
                />
              </div>

              {/* Strict Match toggle */}
              <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.isStrict}
                    onChange={(e) => setFormData({ ...formData, isStrict: e.target.checked })}
                    className="rounded text-blue-600 focus:ring-blue-500 w-4 h-4"
                  />
                  <span className="font-medium text-gray-800">
                    Khớp chính xác hoa/thường (Exact case sensitive)
                  </span>
                </label>
                <p className="text-xs text-gray-400 pl-6 mt-0.5">
                  Chỉ thay thế khi từ trong câu khớp tuyệt đối chữ hoa/chữ thường.
                </p>
              </div>

              {/* Modal Actions */}
              <div className="pt-3 border-t border-gray-100 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setIsAddModalOpen(false);
                    setEditingTerm(null);
                  }}
                  className="px-4 py-2 text-xs font-medium text-gray-700 hover:bg-gray-100 rounded-md"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md shadow-xs"
                >
                  {editingTerm ? 'Lưu thay đổi' : 'Thêm thuật ngữ'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deletingTermId && (
        <div
          id="delete-confirm-modal"
          className="fixed inset-0 bg-gray-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4"
          onClick={() => setDeletingTermId(null)}
        >
          <div
            className="bg-white rounded-xl max-w-sm w-full p-6 shadow-lg border border-gray-200 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="w-10 h-10 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center mx-auto">
              <Trash2 className="w-5 h-5" />
            </div>
            <div className="text-center">
              <h3 className="font-semibold text-gray-900 text-base">Xác nhận xóa thuật ngữ</h3>
              <p className="text-xs text-gray-500 mt-1">
                Bạn có chắc chắn muốn xóa thuật ngữ này khỏi từ điển LinguaFlow? Hành động này không thể hoàn tác.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-2 pt-2">
              <button
                onClick={() => setDeletingTermId(null)}
                className="py-2 text-xs font-medium text-gray-700 hover:bg-gray-100 rounded-md border border-gray-300"
              >
                Hủy bỏ
              </button>
              <button
                onClick={handleConfirmDelete}
                className="py-2 text-xs font-medium text-white bg-rose-600 hover:bg-rose-700 rounded-md shadow-xs"
              >
                Xóa vĩnh viễn
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Import Modal */}
      {isImportModalOpen && (
        <div
          id="import-glossary-modal"
          className="fixed inset-0 bg-gray-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4"
          onClick={() => setIsImportModalOpen(false)}
        >
          <div
            className="bg-white rounded-xl max-w-lg w-full p-6 shadow-lg border border-gray-200 space-y-4 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div>
                <h3 className="font-semibold text-gray-900 text-base">Import Thuật ngữ hàng loạt</h3>
                <p className="text-xs text-gray-400 mt-0.5">Hỗ trợ định dạng CSV hoặc JSON</p>
              </div>
              <button
                onClick={() => setIsImportModalOpen(false)}
                className="text-gray-400 hover:text-gray-700 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <p className="text-gray-600">
                Dán nội dung CSV (mỗi dòng một thuật ngữ: <code className="bg-gray-100 px-1 py-0.5 rounded text-gray-800">Source, Target, SourceLang, TargetLang, Category...</code>) hoặc một mảng JSON:
              </p>

              <textarea
                rows={7}
                value={importText}
                onChange={(e) => setImportText(e.target.value)}
                placeholder={`Prompt Injection, Tiêm nhiễm câu lệnh, EN, VI, Công nghệ & AI, Bắt buộc (High)
Fine-tuning, Tinh chỉnh mô hình, EN, VI, Công nghệ & AI, Bắt buộc (High)
Semantic Search, Tìm kiếm ngữ nghĩa, EN, VI, Công nghệ & AI, Khuyên dùng (Medium)`}
                className="w-full p-3 font-mono text-xs bg-white border border-gray-300 rounded-md outline-hidden focus:border-blue-600"
              />

              <div className="p-3 bg-blue-50/60 rounded-lg border border-blue-100 text-xs text-blue-800">
                Hệ thống tự động phát hiện định dạng, kiểm tra trùng lặp và phân loại chuyên ngành theo chuẩn từ điển LinguaFlow.
              </div>
            </div>

            <div className="pt-3 border-t border-gray-100 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setIsImportModalOpen(false)}
                className="px-4 py-2 text-xs font-medium text-gray-700 hover:bg-gray-100 rounded-md"
              >
                Đóng
              </button>
              <button
                type="button"
                onClick={handleProcessImport}
                className="px-4 py-2 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md shadow-xs"
              >
                Bắt đầu Nhập dữ liệu
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
