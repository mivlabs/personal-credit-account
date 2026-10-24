import type { ThemeConfig } from 'antd';
// Графит как основной цвет действий, лайм только как акцент в CSS; красный/зелёный/оранжевый остаются за статусами.
export const theme: ThemeConfig = {
 token: {
  colorPrimary:'#141414', colorPrimaryHover:'#2E2E2C', colorPrimaryActive:'#000000',
  colorInfo:'#2A48A3', colorSuccess:'#1F8A4C', colorWarning:'#C2660A', colorError:'#D5281F',
  colorLink:'#141414', colorLinkHover:'#5C5C58', colorLinkActive:'#000000',
  colorText:'#141414', colorTextSecondary:'#5C5C58', colorTextTertiary:'#8A8A85', colorTextQuaternary:'#B5B5B0',
  colorBorder:'#DEDED9', colorBorderSecondary:'#ECECE8', colorBgLayout:'#F3F3F1', colorBgContainer:'#FFFFFF', colorFillAlter:'#FAFAF8',
  borderRadius:12, borderRadiusLG:16, borderRadiusSM:8, controlHeight:40, controlHeightLG:48, controlHeightSM:32,
  fontFamily:"'Manrope Variable', Inter, Arial, sans-serif", fontSize:14, lineHeight:1.5,
 },
 components: {
  Button:{ borderRadius:999, borderRadiusLG:999, borderRadiusSM:999, fontWeight:600, paddingInline:20, paddingInlineLG:24, primaryShadow:'none', defaultShadow:'none', defaultBorderColor:'#141414', defaultColor:'#141414', dangerShadow:'none' },
  Card:{ borderRadiusLG:16, paddingLG:24, headerFontSize:15, headerHeight:60 },
  Table:{ headerBg:'transparent', headerColor:'#5C5C58', headerSplitColor:'transparent', borderColor:'#ECECE8', rowHoverBg:'#FAFAF8', cellPaddingBlock:14, cellPaddingInline:12 },
  Tag:{ borderRadiusSM:999 },
  Steps:{ iconSize:28 },
  Alert:{ borderRadiusLG:12 },
  Form:{ labelColor:'#5C5C58', labelFontSize:13, verticalLabelPadding:'0 0 6px' },
  Input:{ paddingBlock:8, paddingInline:14 },
  InputNumber:{ paddingBlock:8, paddingInline:14 },
  Select:{ optionSelectedBg:'#F2FBC6' },
  Timeline:{ dotBorderWidth:2 },
  Layout:{ headerBg:'#F3F3F1', bodyBg:'#F3F3F1', footerBg:'#F3F3F1', headerPadding:'0 32px' },
  Result:{ titleFontSize:22 },
 },
};
