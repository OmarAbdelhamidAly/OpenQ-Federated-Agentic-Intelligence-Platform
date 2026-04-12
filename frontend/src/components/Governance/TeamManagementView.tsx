import { useState, useEffect } from 'react';
import { Users, UserPlus, Search, Filter, Trash2, Loader2 } from 'lucide-react';
import { UserAPI, DataSourcesAPI, GroupsAPI } from '../../services/api';
import type { User, DataSource } from '../../types';

export default function TeamManagementView() {
  const [team, setTeam] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [groups, setGroups] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<'principals' | 'groups'>('principals');
  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [isGroupCreateOpen, setIsGroupCreateOpen] = useState(false);
  const [allSources, setAllSources] = useState<DataSource[]>([]);
  
  // Form States
  const [inviteEmail, setInviteEmail] = useState('');
  const [invitePassword, setInvitePassword] = useState('TemporaryPassword123!');
  const [inviteRole, setInviteRole] = useState<'admin' | 'viewer'>('viewer');
  const [inviteGroupId, setInviteGroupId] = useState('');
  
  const [newGroupName, setNewGroupName] = useState('');
  const [newGroupDesc, setNewGroupDesc] = useState('');
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);

  const fetchTeam = async () => {
    try {
      setLoading(true);
      const users = await UserAPI.list();
      setTeam(users);
      
      // Fetch Groups
      const groupsData = await GroupsAPI.list();
      setGroups(groupsData);

      // Fetch All Available Data Sources
      const sources = await DataSourcesAPI.list();
      setAllSources(sources);
    } catch (e) {
      console.error("Failed to fetch team data", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTeam();
  }, []);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      await UserAPI.invite(inviteEmail, inviteRole, invitePassword, inviteGroupId || undefined);
      alert("User account created! They can now log in immediately.");
      setIsInviteOpen(false);
      fetchTeam();
    } catch (e) {
      alert("Failed to invite user.");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateGroup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newGroupName.trim()) return;
    try {
      setLoading(true);
      await GroupsAPI.create({ 
        name: newGroupName, 
        description: newGroupDesc,
        permissions: {
          accessible_sources: selectedSourceIds
        }
      });
      alert("Success: Tactical group has been forged!");
      setIsGroupCreateOpen(false);
      setNewGroupName('');
      setNewGroupDesc('');
      setSelectedSourceIds([]);
      fetchTeam();
    } catch (e: any) {
      console.error("Failed to create group", e);
      alert(e.response?.data?.detail || "Failed to forge group. Ensure you have admin protocols.");
    } finally {
      setLoading(false);
    }
  };

  const handleRemove = async (id: string) => {
    if (!confirm("Are you sure you want to remove this principal?")) return;
    try {
      await UserAPI.remove(id);
      fetchTeam();
    } catch (e) {
      alert("Failed to remove user.");
    }
  };

  const handleDeleteGroup = async (id: string) => {
    if (!confirm("Delete group? Members will be unassigned.")) return;
    try {
      setLoading(true);
      await GroupsAPI.delete(id);
      alert("Group disbanded successfully.");
      fetchTeam();
    } catch (e) {
      console.error("Failed to delete group", e);
      alert("Failed to delete group.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto custom-scroll bg-[#0a0d17]/50 relative">
      <div className="p-8 pb-12 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-[var(--primary)]/5 blur-[120px] rounded-full -translate-y-1/2 translate-x-1/2"></div>
        
        <div className="relative z-10 flex items-end justify-between">
          <div>
             <div className="flex items-center gap-3 mb-4">
                <div className="p-2 rounded-xl bg-[var(--primary)]/10 border border-[var(--primary)]/20">
                   <Users className="w-5 h-5 text-[var(--primary)]" />
                </div>
                <span className="text-[10px] font-black text-[var(--primary)] uppercase tracking-[0.3em]">Identity & Access Management</span>
             </div>
             <h1 className="text-4xl font-black text-white tracking-tight">Team Management</h1>
             <p className="text-slate-400 mt-2 font-medium max-w-xl">
                Manage organizational hierarchy, groups, and cross-team collaboration protocols.
             </p>
          </div>

          <div className="flex gap-4">
            <button 
              onClick={() => setIsGroupCreateOpen(true)}
              className="bg-white/5 hover:bg-white/10 text-white border border-white/10 px-6 py-3 rounded-2xl text-sm font-bold transition-all flex items-center gap-2"
            >
              New Group
            </button>
            <button 
              onClick={() => setIsInviteOpen(true)}
              className="bg-[var(--primary)] hover:bg-[var(--primary-glow)] text-white px-6 py-3 rounded-2xl text-sm font-bold shadow-xl shadow-[var(--primary)]/20 transition-all flex items-center gap-2 group"
            >
              <UserPlus className="w-4 h-4 group-hover:scale-110 transition-transform" /> Create User
            </button>
          </div>
        </div>
      </div>

      <div className="px-8 pb-4 flex gap-8 border-b border-slate-800 mx-8 mb-8">
        <button 
          onClick={() => setActiveTab('principals')}
          className={`pb-4 text-xs font-black uppercase tracking-widest transition-all relative ${activeTab === 'principals' ? 'text-white' : 'text-slate-500 hover:text-white'}`}
        >
          Principals
          {activeTab === 'principals' && <div className="absolute bottom-0 left-0 w-full h-0.5 bg-[var(--primary)]"></div>}
        </button>
        <button 
          onClick={() => setActiveTab('groups')}
          className={`pb-4 text-xs font-black uppercase tracking-widest transition-all relative ${activeTab === 'groups' ? 'text-white' : 'text-slate-500 hover:text-white'}`}
        >
          Groups
          {activeTab === 'groups' && <div className="absolute bottom-0 left-0 w-full h-0.5 bg-[var(--primary)]"></div>}
        </button>
      </div>

      <div className="px-8 pb-12">
        <div className="bg-slate-900/40 border border-slate-800 rounded-[32px] overflow-hidden backdrop-blur-xl transition-all hover:border-[var(--primary)]/20">
          {activeTab === 'principals' ? (
            <>
              <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-white/5">
                <div className="flex items-center gap-6">
                   <div className="relative">
                     <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                     <input 
                       placeholder="Search principals..." 
                       className="bg-black/20 border border-slate-700/50 rounded-xl py-2 pl-10 pr-4 text-xs font-bold text-white focus:outline-none focus:border-[var(--primary)]/50 transition-all w-64"
                     />
                   </div>
                   <button className="flex items-center gap-2 text-[10px] font-black text-slate-500 uppercase tracking-widest hover:text-white transition-colors">
                      <Filter className="w-3.5 h-3.5" /> Filter
                   </button>
                </div>
                <span className="text-[10px] text-slate-600 font-bold uppercase tracking-widest">{team.length} Active Principals</span>
              </div>

              <div className="overflow-x-auto">
                {loading ? (
                  <div className="p-12 flex flex-col items-center gap-4">
                    <Loader2 className="w-8 h-8 text-[var(--primary)] animate-spin" />
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">Fetching team metadata...</p>
                  </div>
                ) : (
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-slate-800 bg-black/10">
                        <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Principal</th>
                        <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Group</th>
                        <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Role</th>
                        <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Status</th>
                        <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/50">
                      {team.map((member) => (
                        <tr key={member.id} className="hover:bg-[var(--primary)]/5 transition-all cursor-pointer group">
                          <td className="px-6 py-5">
                            <div className="flex items-center gap-4">
                              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--primary)]/20 to-[var(--primary-alt)]/20 border border-[var(--primary)]/20 flex items-center justify-center font-black text-[var(--primary)] text-xs shadow-inner">
                                {(member.email || '?').charAt(0).toUpperCase()}
                              </div>
                              <div>
                                <p className="text-sm font-black text-white group-hover:text-[var(--primary)] transition-colors">{(member.email || 'N/A').split('@')[0]}</p>
                                <span className="text-[10px] font-bold text-slate-500">{member.email || 'No email provided'}</span>
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-5">
                            <span className="text-[10px] font-black uppercase text-slate-400 border border-slate-800 px-2 py-1 rounded-md">
                              {groups.find(g => g.id === member.group_id)?.name || 'No Group'}
                            </span>
                          </td>
                          <td className="px-6 py-5">
                            <span className="text-xs font-bold text-slate-300 uppercase">{member.role}</span>
                          </td>
                          <td className="px-6 py-5">
                            <div className="flex items-center gap-2">
                              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500"></div>
                              <span className="text-[10px] font-black text-emerald-400">Authorized</span>
                            </div>
                          </td>
                          <td className="px-6 py-5 text-right">
                             <button 
                               onClick={(e) => { e.stopPropagation(); handleRemove(member.id); }}
                               className="p-2 text-slate-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
                             >
                                <Trash2 className="w-4 h-4" />
                             </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 bg-black/10">
                    <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Group Name</th>
                    <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Members</th>
                    <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Permissions</th>
                    <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {groups.map((group) => (
                    <tr key={group.id} className="hover:bg-[var(--primary)]/5 transition-all cursor-pointer group">
                      <td className="px-6 py-5">
                        <p className="text-sm font-black text-white group-hover:text-[var(--primary)]">{group.name}</p>
                        <p className="text-[10px] text-slate-500">{group.description || 'No description'}</p>
                      </td>
                      <td className="px-6 py-5">
                        <span className="text-xs font-bold text-slate-300">{group.member_count} users</span>
                      </td>
                      <td className="px-6 py-5">
                        <div className="flex flex-wrap gap-1.5 uppercase">
                          {group.permissions?.accessible_sources?.length > 0 && (
                            <span className="text-[8px] font-black bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-1.5 py-0.5 rounded">
                              {group.permissions.accessible_sources.length} Resources
                            </span>
                          )}
                          {Object.keys(group.permissions).filter(k => k !== 'accessible_sources').length > 0 ? (
                            Object.keys(group.permissions).filter(k => k !== 'accessible_sources').map(p => (
                              <span key={p} className="text-[8px] font-black bg-blue-500/10 text-blue-400 border border-blue-500/20 px-1.5 py-0.5 rounded uppercase">{p}</span>
                            ))
                          ) : (
                            !group.permissions?.accessible_sources?.length && (
                              <span className="text-[10px] text-slate-600 font-bold uppercase tracking-widest italic">Standard Access</span>
                            )
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-5 text-right">
                         <button 
                           onClick={(e) => { e.stopPropagation(); handleDeleteGroup(group.id); }}
                           className="p-2 text-slate-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
                         >
                           <Trash2 className="w-4 h-4" />
                         </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Invite Modal */}
      {isInviteOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-md">
          <div className="bg-slate-900 border border-slate-800 rounded-[32px] w-full max-w-md p-8 shadow-2xl relative">
            <h2 className="text-2xl font-black text-white mb-6">Create New Principal</h2>
            <form onSubmit={handleInvite} className="space-y-4">
              <div>
                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Email Address</label>
                <input 
                  type="email" required value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)}
                  className="w-full bg-black/40 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:border-[var(--primary)] outline-none"
                  placeholder="name@company.com"
                />
              </div>
              <div>
                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Initial Password</label>
                <input 
                  type="text" required value={invitePassword} onChange={(e) => setInvitePassword(e.target.value)}
                  className="w-full bg-black/40 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:border-[var(--primary)] outline-none"
                  placeholder="At least 8 characters"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Role</label>
                  <select 
                    value={inviteRole} onChange={(e) => setInviteRole(e.target.value as any)}
                    className="w-full bg-black/40 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:border-[var(--primary)] outline-none appearance-none"
                  >
                    <option value="viewer">Viewer</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Group</label>
                  <select 
                    value={inviteGroupId} onChange={(e) => setInviteGroupId(e.target.value)}
                    className="w-full bg-black/40 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:border-[var(--primary)] outline-none appearance-none"
                  >
                    <option value="">No Group</option>
                    {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
                  </select>
                </div>
              </div>
              <div className="flex gap-4 pt-4">
                <button type="button" onClick={() => setIsInviteOpen(false)} className="flex-1 px-6 py-3 rounded-2xl text-xs font-bold text-slate-400 hover:text-white transition-all">Cancel</button>
                <button type="submit" className="flex-1 bg-[var(--primary)] text-white px-6 py-3 rounded-2xl text-xs font-bold shadow-lg shadow-[var(--primary)]/20">Activate Account</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Group Create Modal */}
      {isGroupCreateOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-md">
          <div className="bg-slate-900 border border-slate-800 rounded-[32px] w-full max-w-md p-8 shadow-2xl relative">
            <h2 className="text-2xl font-black text-white mb-6">Forge New Group</h2>
            <form onSubmit={handleCreateGroup} className="space-y-4">
              <div>
                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Group Name</label>
                <input 
                  required value={newGroupName} onChange={(e) => setNewGroupName(e.target.value)}
                  className="w-full bg-black/40 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:border-[var(--primary)] outline-none"
                  placeholder="e.g. Finance Analytics"
                />
              </div>
              <div>
                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Description</label>
                <textarea 
                  value={newGroupDesc} onChange={(e) => setNewGroupDesc(e.target.value)}
                  className="w-full bg-black/40 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:border-[var(--primary)] outline-none h-24"
                  placeholder="Define the group scope..."
                />
              </div>

              <div>
                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5 flex items-center justify-between">
                  Accessible Resources
                  <span className="text-[var(--primary)] lowercase tracking-normal">({selectedSourceIds.length} selected)</span>
                </label>
                <div className="bg-black/40 border border-slate-800 rounded-xl max-h-48 overflow-y-auto custom-scroll p-2 space-y-1">
                  {allSources.length === 0 ? (
                    <div className="p-4 text-center">
                      <p className="text-[10px] font-bold text-slate-600 uppercase tracking-widest">No files found</p>
                    </div>
                  ) : (
                    allSources.map(source => (
                      <div 
                        key={source.id}
                        onClick={() => {
                          setSelectedSourceIds(prev => 
                            prev.includes(source.id) 
                              ? prev.filter(id => id !== source.id) 
                              : [...prev, source.id]
                          );
                        }}
                        className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all border ${
                          selectedSourceIds.includes(source.id) 
                            ? 'bg-[var(--primary)]/10 border-[var(--primary)]/30' 
                            : 'hover:bg-white/5 border-transparent'
                        }`}
                      >
                        <div className={`w-4 h-4 rounded border flex items-center justify-center transition-all ${
                          selectedSourceIds.includes(source.id) ? 'bg-[var(--primary)] border-[var(--primary)]' : 'border-slate-700'
                        }`}>
                          {selectedSourceIds.includes(source.id) && <div className="w-1.5 h-1.5 bg-white rounded-full"></div>}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className={`text-[11px] font-bold truncate ${selectedSourceIds.includes(source.id) ? 'text-white' : 'text-slate-400'}`}>
                            {source.name}
                          </p>
                          <p className="text-[9px] text-slate-500 uppercase font-black tracking-tighter">{source.type}</p>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="flex gap-4 pt-4">
                <button type="button" onClick={() => setIsGroupCreateOpen(false)} className="flex-1 px-6 py-3 rounded-2xl text-xs font-bold text-slate-400 hover:text-white transition-all">Cancel</button>
                <button type="submit" className="flex-1 bg-[var(--primary)] text-white px-6 py-3 rounded-2xl text-xs font-bold shadow-lg shadow-[var(--primary)]/20">Create Group</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
