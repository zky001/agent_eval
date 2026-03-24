import React from "react";
import { Routes, Route, useNavigate, useLocation } from "react-router-dom";
import { Layout, Menu, Typography } from "antd";
import {
  DashboardOutlined,
  DatabaseOutlined,
  RobotOutlined,
  PlayCircleOutlined,
  TrophyOutlined,
  PlusCircleOutlined,
} from "@ant-design/icons";
import DashboardPage from "./pages/DashboardPage";
import DatasetsPage from "./pages/DatasetsPage";
import DatasetDetailPage from "./pages/DatasetDetailPage";
import ModelsPage from "./pages/ModelsPage";
import RunsListPage from "./pages/RunsListPage";
import NewRunPage from "./pages/NewRunPage";
import RunDetailPage from "./pages/RunDetailPage";
import LeaderboardPage from "./pages/LeaderboardPage";

const { Sider, Content, Header } = Layout;

const menuItems = [
  { key: "/", icon: <DashboardOutlined />, label: "Dashboard" },
  { key: "/datasets", icon: <DatabaseOutlined />, label: "Datasets" },
  { key: "/models", icon: <RobotOutlined />, label: "Models" },
  { key: "/runs/new", icon: <PlusCircleOutlined />, label: "New Run" },
  { key: "/runs", icon: <PlayCircleOutlined />, label: "Evaluation Runs" },
  { key: "/leaderboard", icon: <TrophyOutlined />, label: "Leaderboard" },
];

const App: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const selectedKey = (() => {
    const path = location.pathname;
    if (path === "/") return "/";
    if (path.startsWith("/datasets")) return "/datasets";
    if (path === "/runs/new") return "/runs/new";
    if (path.startsWith("/runs")) return "/runs";
    if (path.startsWith("/models")) return "/models";
    if (path.startsWith("/leaderboard")) return "/leaderboard";
    return "/";
  })();

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        width={220}
        style={{
          background: "#001529",
          overflow: "auto",
          height: "100vh",
          position: "fixed",
          left: 0,
          top: 0,
          bottom: 0,
        }}
      >
        <div
          style={{
            height: 64,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderBottom: "1px solid rgba(255,255,255,0.1)",
          }}
        >
          <Typography.Title
            level={4}
            style={{ color: "#fff", margin: 0, whiteSpace: "nowrap" }}
          >
            Agent Eval
          </Typography.Title>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ borderRight: 0 }}
        />
      </Sider>
      <Layout style={{ marginLeft: 220 }}>
        <Header
          style={{
            background: "#fff",
            padding: "0 24px",
            borderBottom: "1px solid #f0f0f0",
            display: "flex",
            alignItems: "center",
          }}
        >
          <Typography.Title level={4} style={{ margin: 0 }}>
            Agent Evaluation Platform
          </Typography.Title>
        </Header>
        <Content style={{ margin: 24, minHeight: 280 }}>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/datasets" element={<DatasetsPage />} />
            <Route path="/datasets/:id" element={<DatasetDetailPage />} />
            <Route path="/models" element={<ModelsPage />} />
            <Route path="/runs/new" element={<NewRunPage />} />
            <Route path="/runs" element={<RunsListPage />} />
            <Route path="/runs/:id" element={<RunDetailPage />} />
            <Route path="/leaderboard" element={<LeaderboardPage />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
};

export default App;
