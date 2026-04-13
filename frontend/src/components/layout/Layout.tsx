import Sidebar from './Sidebar'

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <Sidebar />
      {/* Main scrollable content area */}
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  )
}
