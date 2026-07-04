import { Navigate } from 'react-router-dom';
import { useRecoilValue } from 'recoil';

import {
  sideViewState,
  useAuth,
  useChatData,
  useConfig
} from '@chainlit/react-client';

import ChatSettingsSidebar from '@/components/ChatSettings/ChatSettingsSidebar';
import ElementSideView from '@/components/ElementSideView';
import LeftSidebar from '@/components/LeftSidebar';
import { TaskList } from '@/components/Tasklist';
import { Header } from '@/components/header';
import { ResizablePanel, ResizablePanelGroup } from '@/components/ui/resizable';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';

import { chatSettingsSidebarOpenState } from '@/state/project';
import { userEnvState } from 'state/user';

type Props = {
  children: JSX.Element;
};

const Page = ({ children }: Props) => {
  const { config } = useConfig();
  const { data } = useAuth();
  const { chatSettingsInputs } = useChatData();
  const userEnv = useRecoilValue(userEnvState);
  const sideView = useRecoilValue(sideViewState);
  const chatSettingsSidebarOpen = useRecoilValue(chatSettingsSidebarOpenState);

  if (config?.userEnv) {
    for (const key of config.userEnv || []) {
      if (!userEnv[key]) return <Navigate to="/env" />;
    }
  }

  const showSettingsSidebar =
    config?.ui?.chat_settings_location === 'sidebar' &&
    chatSettingsSidebarOpen &&
    chatSettingsInputs.length > 0;
  const settingsSidebarSize = showSettingsSidebar ? 25 : 0;
  const preferredSideViewSize = sideView
    ? sideView.title === 'canvas'
      ? 50
      : 40
    : 0;
  const sideViewSize = sideView
    ? Math.max(10, Math.min(preferredSideViewSize, 60 - settingsSidebarSize))
    : 0;
  const mainPanelSize = 100 - sideViewSize - settingsSidebarSize;

  const mainContent = (
    <div className="flex flex-col h-full w-full">
      <Header />
      <ResizablePanelGroup
        direction="horizontal"
        className="flex flex-row flex-grow"
      >
        <ResizablePanel
          className="flex flex-col h-full w-full"
          minSize={40}
          defaultSize={mainPanelSize}
        >
          <div className="flex flex-row flex-grow overflow-auto">
            {children}
          </div>
        </ResizablePanel>
        {sideView ? (
          <ElementSideView defaultSize={sideViewSize} />
        ) : (
          <TaskList isMobile={false} />
        )}
        {showSettingsSidebar && (
          <ChatSettingsSidebar defaultSize={settingsSidebarSize} />
        )}
      </ResizablePanelGroup>
    </div>
  );

  const historyEnabled = config?.dataPersistence && data?.requireLogin;
  const sidebarHidden = config?.ui?.default_sidebar_state === 'hidden';

  return (
    <SidebarProvider
      defaultOpen={config?.ui.default_sidebar_state !== 'closed'}
    >
      {historyEnabled && !sidebarHidden ? (
        <>
          <LeftSidebar />
          <SidebarInset className="max-h-svh min-w-0">
            {mainContent}
          </SidebarInset>
        </>
      ) : (
        <div className="h-screen w-screen flex">{mainContent}</div>
      )}
    </SidebarProvider>
  );
};

export default Page;
